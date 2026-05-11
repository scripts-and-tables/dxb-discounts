"""Auto-merge cross-source duplicate Places per data/place_duplicates_enriched.json.

Runs the rules already encoded in the audit: for each cluster with
`auto_merge: true`, picks the canonical Place (richest data), re-points
all of the loser's Discounts onto it, copies useful loser fields into
empty canonical fields, and soft-deletes the loser via
`is_published=False`. The Place row stays in the DB so the old slug
remains reachable from Django admin.

Dry-run by default. Pass --apply to actually mutate the DB.

Use --include-reviewed to also apply medium-confidence clusters whose
`auto_merge` flag has been flipped to true by hand in the JSON.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.discounts.models import Discount
from apps.places.models import Place


SRC = Path(__file__).resolve().parents[4] / "data" / "place_duplicates_enriched.json"

# Fields we copy loser -> canonical, but only when canonical's value is empty.
# Never overwrite curator-set data.
COPY_FIELDS = (
    "website", "address", "phone", "description",
    "logo_url_override", "lat", "lng",
)


def _is_empty(v) -> bool:
    return v is None or v == ""


def _pick_canonical(places_by_id: dict, place_ids: list[int]) -> Place:
    """Choose the richer Place by: more discounts -> has coords -> has address
    -> has logo override -> oldest id."""
    candidates = [places_by_id[i] for i in place_ids if i in places_by_id]
    def sort_key(p):
        active = Discount.objects.filter(place=p, is_active=True).count()
        return (
            -active,
            0 if p.lat is not None and p.lng is not None else 1,
            0 if p.address else 1,
            0 if p.logo_url_override else 1,
            p.id,
        )
    candidates.sort(key=sort_key)
    return candidates[0]


def _merge_one(cluster: dict, places_by_id: dict, dry_run: bool, stdout) -> dict:
    place_ids = [p["id"] for p in cluster["places"]]
    if any(pid not in places_by_id for pid in place_ids):
        stdout.write(f"  SKIP {cluster['cluster_id']!r}: a Place id is missing in the DB")
        return {"skipped_missing": 1}

    canonical = _pick_canonical(places_by_id, place_ids)
    losers = [places_by_id[pid] for pid in place_ids if pid != canonical.id]

    summary = {"canonical_id": canonical.id, "loser_ids": [l.id for l in losers],
               "discounts_moved": 0, "fields_copied": []}

    for loser in losers:
        # Field backfill (only into empty canonical fields).
        changed: list[str] = []
        for field in COPY_FIELDS:
            cval = getattr(canonical, field)
            lval = getattr(loser, field)
            if _is_empty(cval) and not _is_empty(lval):
                if not dry_run:
                    setattr(canonical, field, lval)
                changed.append(field)
        if changed and not dry_run:
            canonical.save(update_fields=changed)
        summary["fields_copied"].extend(f"{field}<-{loser.id}" for field in changed)

        # Union experiences (M2M).
        if not dry_run:
            loser_exps = list(loser.experiences.all())
            if loser_exps:
                canonical.experiences.add(*loser_exps)

        # Preserve aggregates_branches / is_members_only if either side has it.
        if not dry_run:
            if loser.aggregates_branches and not canonical.aggregates_branches:
                canonical.aggregates_branches = True
                canonical.save(update_fields=["aggregates_branches"])
            if loser.is_members_only and not canonical.is_members_only:
                canonical.is_members_only = True
                canonical.save(update_fields=["is_members_only"])

        # Re-point discounts. update() bypasses save() but that's fine — the
        # Discount.save override only fills the slug, which is already set.
        qs = Discount.objects.filter(place=loser)
        moved = qs.count()
        if not dry_run:
            qs.update(place=canonical)
        summary["discounts_moved"] += moved

        # Soft-delete the loser.
        if not dry_run:
            Place.objects.filter(id=loser.id).update(is_published=False)

    return summary


class Command(BaseCommand):
    help = "Merge cross-source duplicate Places per data/place_duplicates_enriched.json."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="actually write to the DB (default is dry-run)")
        parser.add_argument("--include-reviewed", action="store_true",
                            help="also apply clusters whose auto_merge was flipped to true by hand")

    def handle(self, *args, apply: bool, include_reviewed: bool, **kwargs):
        if not SRC.exists():
            self.stderr.write(f"enriched file not found: {SRC}\nRun audit_place_duplicates.py first.")
            return

        clusters = json.loads(SRC.read_text(encoding="utf-8"))
        # Filter to the clusters we'd touch.
        eligible = [
            c for c in clusters
            if c.get("auto_merge") and (c.get("confidence") == "high" or include_reviewed)
        ]
        self.stdout.write(f"loaded {len(clusters)} clusters; {len(eligible)} eligible for merge")

        place_ids = {p["id"] for c in eligible for p in c["places"]}
        places_by_id = {p.id: p for p in Place.objects.filter(id__in=place_ids)}

        totals = {"clusters_merged": 0, "discounts_moved": 0, "losers_unpublished": 0, "skipped": 0}

        for cluster in eligible:
            self.stdout.write(f"\n[{cluster['cluster_id']!r}] (confidence={cluster['confidence']})")
            with transaction.atomic():
                summary = _merge_one(cluster, places_by_id, dry_run=not apply, stdout=self.stdout)
                if not apply:
                    transaction.set_rollback(True)
            if "skipped_missing" in summary:
                totals["skipped"] += 1
                continue
            totals["clusters_merged"] += 1
            totals["discounts_moved"] += summary["discounts_moved"]
            totals["losers_unpublished"] += len(summary["loser_ids"])
            self.stdout.write(
                f"  canonical={summary['canonical_id']} "
                f"losers={summary['loser_ids']} "
                f"discounts_moved={summary['discounts_moved']} "
                f"fields_copied={summary['fields_copied']}"
            )

        self.stdout.write("\n--- Summary ---")
        self.stdout.write(f"  clusters merged:     {totals['clusters_merged']}")
        self.stdout.write(f"  losers unpublished:  {totals['losers_unpublished']}")
        self.stdout.write(f"  discounts re-pointed:{totals['discounts_moved']}")
        self.stdout.write(f"  clusters skipped:    {totals['skipped']}")
        if not apply:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes committed. Pass --apply to write."))
