"""One-shot: apply data/place_icons_enriched.json to the production DB.

Background: the refresh-icons skill was run locally against the SQLite
dev DB, populating Place.logo_url_override for 6,971 places (Entertainer
+ Fazaa direct CDN logos) and backfilling Place.website for 26 more
(Clearbit Autocomplete + Playbook matches). Production never received
that import because the applier (`scripts/import_place_icons.py`) only
talked to whichever DATABASE_URL it was invoked with — i.e. local.

This migration replays the same `decide()` policy used by the applier
script, matching rows by `slug` (stable across DBs; ids drift).

Apply rules per row in data/place_icons_enriched.json:
- source=entertainer | fazaa | html_parse  -> set logo_url_override
- source=playbook                          -> backfill website
- source=clearbit_autocomplete + high conf -> backfill website
- source=clearbit_autocomplete + low conf  -> SKIP (manual review)
- source=icon_horse | none                 -> SKIP

Idempotent: targets already populated on the row are left alone (no
--force equivalent here; manual edits stay).
"""
import json
from pathlib import Path

from django.db import migrations


SRC = Path(__file__).resolve().parent.parent.parent.parent / "data" / "place_icons_enriched.json"


def _decision(row: dict) -> dict | None:
    source = row.get("source")
    confidence = row.get("confidence")
    sug_site = (row.get("suggested_website") or "").strip()
    sug_logo = (row.get("suggested_logo_url") or "").strip()
    if source in ("entertainer", "fazaa", "html_parse"):
        return {"logo_url_override": sug_logo} if sug_logo else None
    if source == "playbook":
        return {"website": sug_site} if sug_site else None
    if source == "clearbit_autocomplete" and confidence == "high":
        return {"website": sug_site} if sug_site else None
    return None


def apply_resolved_icons(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    if not SRC.exists():
        # The data file may have been removed in a follow-up commit after
        # this migration applied to prod. That's fine — re-running a noop
        # is the correct behavior.
        print(f"[0011_apply_place_icons] {SRC.name} not present; skipping.")
        return

    rows = json.loads(SRC.read_text(encoding="utf-8"))
    slugs = [r["slug"] for r in rows if r.get("slug")]
    by_slug = {p.slug: p for p in Place.objects.filter(slug__in=slugs)}

    updates: list = []
    counts = {"override": 0, "website": 0, "skipped_already": 0, "skipped_no_match": 0, "skipped_no_decision": 0}
    for row in rows:
        decision = _decision(row)
        if not decision:
            counts["skipped_no_decision"] += 1
            continue
        place = by_slug.get(row.get("slug"))
        if place is None:
            counts["skipped_no_match"] += 1
            continue

        touched = False
        if "logo_url_override" in decision and not place.logo_url_override:
            place.logo_url_override = decision["logo_url_override"]
            counts["override"] += 1
            touched = True
        if "website" in decision and not place.website:
            place.website = decision["website"]
            counts["website"] += 1
            touched = True
        if touched:
            updates.append(place)
        else:
            counts["skipped_already"] += 1

    if updates:
        Place.objects.bulk_update(updates, ["website", "logo_url_override"], batch_size=500)

    print(
        f"[0011_apply_place_icons] rows={len(rows)} updates={len(updates)} "
        f"(override={counts['override']} website={counts['website']}) "
        f"skipped_already={counts['skipped_already']} "
        f"skipped_no_match={counts['skipped_no_match']} "
        f"skipped_no_decision={counts['skipped_no_decision']}"
    )


def noop_reverse(apps, schema_editor):
    """Reverse leaves the DB as-is. We don't want to silently null out
    logo overrides on rollback — manual cleanup if needed."""
    return


class Migration(migrations.Migration):

    dependencies = [
        ("places", "0010_add_logo_url_override"),
    ]

    operations = [
        migrations.RunPython(apply_resolved_icons, noop_reverse),
    ]
