"""Apply data/place_icons_enriched.json to the Place table.

Rules:
- source=entertainer       -> set Place.logo_url_override (direct CDN URL).
- source=playbook          -> backfill Place.website from `suggested_website`
                              when it's empty. No override needed: the new
                              `logo_url` property will derive icon.horse
                              from the domain automatically.
- source=clearbit_autocomplete + confidence=high
                           -> backfill Place.website. Same icon.horse-from-
                              domain pathway as Playbook.
- source=clearbit_autocomplete + confidence=low  -> SKIP (manual review).
- source=html_parse        -> set Place.logo_url_override (specific image
                              URL from <head>; can't be re-derived).
- source=icon_horse        -> SKIP (logo_url already derives the same URL
                              from the existing website domain).
- source=none              -> SKIP.

By default, only Places whose `logo_url_override` is empty AND/OR whose
`website` is empty get touched (idempotent re-runs). Pass --force to
overwrite already-set values.

Dry-run by default. Pass --apply to actually write to the DB.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import django

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "place_icons_enriched.json"


def _boot_django() -> None:
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()


def decide(row: dict) -> dict | None:
    """Return {website, logo_url_override} to apply, or None to skip."""
    source = row.get("source")
    confidence = row.get("confidence")
    sug_site = (row.get("suggested_website") or "").strip()
    sug_logo = (row.get("suggested_logo_url") or "").strip()

    if source == "entertainer":
        return {"logo_url_override": sug_logo} if sug_logo else None

    if source == "playbook":
        return {"website": sug_site} if sug_site else None

    if source == "clearbit_autocomplete" and confidence == "high":
        return {"website": sug_site} if sug_site else None

    if source == "html_parse":
        return {"logo_url_override": sug_logo} if sug_logo else None

    # clearbit_autocomplete (low conf), icon_horse, none -> skip
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true",
                        help="actually write to the DB (default is dry-run)")
    parser.add_argument("--force", action="store_true",
                        help="overwrite Place.website / logo_url_override even when already set")
    parser.add_argument("--limit", type=int, default=None,
                        help="apply only the first N rows (smoke test)")
    args = parser.parse_args()

    if not SRC.exists():
        print(f"enriched file not found: {SRC}\nRun refresh-icons skill first.", file=sys.stderr)
        return 2

    rows = json.loads(SRC.read_text(encoding="utf-8"))
    if args.limit:
        rows = rows[: args.limit]

    _boot_django()
    from apps.places.models import Place  # noqa: E402

    by_id: dict[int, Place] = {p.id: p for p in Place.objects.filter(id__in=[r["id"] for r in rows])}

    updates: list[Place] = []
    counts = {
        "skipped_no_match": 0,
        "skipped_already_set": 0,
        "skipped_missing_in_db": 0,
        "applied_logo_override": 0,
        "applied_website": 0,
        "applied_both": 0,
    }

    for row in rows:
        decision = decide(row)
        if not decision:
            counts["skipped_no_match"] += 1
            continue

        place = by_id.get(row["id"])
        if place is None:
            counts["skipped_missing_in_db"] += 1
            continue

        touched_logo = False
        touched_site = False

        if "logo_url_override" in decision:
            if place.logo_url_override and not args.force:
                counts["skipped_already_set"] += 1
                continue
            if place.logo_url_override != decision["logo_url_override"]:
                place.logo_url_override = decision["logo_url_override"]
                touched_logo = True

        if "website" in decision:
            if place.website and not args.force:
                counts["skipped_already_set"] += 1
                continue
            if place.website != decision["website"]:
                place.website = decision["website"]
                touched_site = True

        if touched_logo and touched_site:
            counts["applied_both"] += 1
        elif touched_logo:
            counts["applied_logo_override"] += 1
        elif touched_site:
            counts["applied_website"] += 1
        else:
            counts["skipped_already_set"] += 1
            continue
        updates.append(place)

    print(f"loaded {len(rows)} enriched rows, matched {len(by_id)} Places in DB")
    print(f"  applied logo_url_override: {counts['applied_logo_override']}")
    print(f"  applied website:           {counts['applied_website']}")
    print(f"  applied both:              {counts['applied_both']}")
    print(f"  skipped (no actionable match): {counts['skipped_no_match']}")
    print(f"  skipped (target already set):  {counts['skipped_already_set']}")
    print(f"  skipped (id not in DB):        {counts['skipped_missing_in_db']}")
    print()

    if not args.apply:
        print(f"[dry-run] would update {len(updates)} Place rows. Pass --apply to write.")
        return 0

    if updates:
        Place.objects.bulk_update(updates, ["website", "logo_url_override"], batch_size=500)
        print(f"updated {len(updates)} Place rows.")
    else:
        print("nothing to update.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
