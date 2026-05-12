"""Auto-merge duplicate Places per data/place_duplicates_enriched.json.

Handles three cluster kinds:
- `cross_source`         — two same-named Places from different sources.
- `brand_with_branches`  — one brand-level Place + N Entertainer branches.
- `synthesizable_branches` — N Entertainer branches with no brand Place;
                             the merger creates a brand-level Place first.

For each cluster, picks (or creates) the canonical Place, re-points all
losers' Discounts onto it via bulk update, copies useful loser fields
into empty canonical fields, and soft-deletes losers via
`is_published=False`. Loser rows stay in the DB so old slugs remain
reachable from admin.

Dry-run by default. Pass --apply to actually mutate.
Use --include-reviewed to also apply medium-conf clusters whose
`auto_merge` flag has been flipped to true by hand.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.discounts.models import Discount
from apps.places.models import Category, Place


SRC = Path(__file__).resolve().parents[4] / "data" / "place_duplicates_enriched.json"

# Fields we copy loser -> canonical, but only when canonical's value is empty.
# Never overwrite curator-set data.
COPY_FIELDS = (
    "website", "address", "phone", "description",
    "logo_url_override", "lat", "lng", "area",
)


def _is_empty(v) -> bool:
    return v is None or v == ""


def _pick_canonical(places_by_id: dict, place_ids: list[int]) -> Place:
    """Choose the richer Place: more active discounts -> has coords -> has
    address -> has logo override -> oldest id."""
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


def _merge_loser_into(canonical: Place, loser: Place, dry_run: bool) -> tuple[int, list[str]]:
    """Move loser's discounts to canonical, backfill canonical's empty fields
    from loser, soft-delete loser. Returns (discounts_moved, fields_copied)."""
    fields_copied: list[str] = []
    for field in COPY_FIELDS:
        cval = getattr(canonical, field)
        lval = getattr(loser, field)
        if _is_empty(cval) and not _is_empty(lval):
            if not dry_run:
                setattr(canonical, field, lval)
            fields_copied.append(field)
    if fields_copied and not dry_run:
        canonical.save(update_fields=fields_copied)

    if not dry_run:
        loser_exps = list(loser.experiences.all())
        if loser_exps:
            canonical.experiences.add(*loser_exps)
        if loser.aggregates_branches and not canonical.aggregates_branches:
            canonical.aggregates_branches = True
            canonical.save(update_fields=["aggregates_branches"])
        if loser.is_members_only and not canonical.is_members_only:
            canonical.is_members_only = True
            canonical.save(update_fields=["is_members_only"])

    qs = Discount.objects.filter(place=loser)
    moved = qs.count()
    if not dry_run:
        qs.update(place=canonical)
        Place.objects.filter(id=loser.id).update(is_published=False)

    return moved, fields_copied


def _merge_cross_source(cluster: dict, places_by_id: dict, dry_run: bool, stdout) -> dict:
    """Existing v1 path: 2 Places same name, different sources. Merge into the
    richer one."""
    place_ids = [p["id"] for p in cluster["places"]]
    if any(pid not in places_by_id for pid in place_ids):
        return {"skipped_missing": 1}
    canonical = _pick_canonical(places_by_id, place_ids)
    losers = [places_by_id[pid] for pid in place_ids if pid != canonical.id]
    summary = {"canonical_id": canonical.id, "loser_ids": [l.id for l in losers],
               "discounts_moved": 0, "fields_copied": []}
    for loser in losers:
        moved, copied = _merge_loser_into(canonical, loser, dry_run)
        summary["discounts_moved"] += moved
        summary["fields_copied"].extend(f"{f}<-{loser.id}" for f in copied)
    return summary


def _merge_brand_with_branches(cluster: dict, places_by_id: dict, dry_run: bool, stdout) -> dict:
    """Brand row exists + N Entertainer branches. Canonical = brand."""
    canonical_id = cluster.get("suggested_canonical_id") or cluster.get("brand_id")
    branch_ids = cluster.get("branch_ids") or []
    if canonical_id is None or canonical_id not in places_by_id:
        return {"skipped_missing": 1}
    if any(bid not in places_by_id for bid in branch_ids):
        return {"skipped_missing": 1}
    canonical = places_by_id[canonical_id]
    branches = [places_by_id[bid] for bid in branch_ids]
    summary = {"canonical_id": canonical_id, "loser_ids": branch_ids,
               "discounts_moved": 0, "fields_copied": []}
    for branch in branches:
        moved, copied = _merge_loser_into(canonical, branch, dry_run)
        summary["discounts_moved"] += moved
        summary["fields_copied"].extend(f"{f}<-{branch.id}" for f in copied)
    return summary


def _merge_synthesizable_branches(cluster: dict, places_by_id: dict, dry_run: bool, stdout) -> dict:
    """No brand row exists; synthesize one named after the cluster prefix,
    then merge all branches into it."""
    branch_ids = cluster.get("branch_ids") or []
    if any(bid not in places_by_id for bid in branch_ids):
        return {"skipped_missing": 1}
    branches = sorted([places_by_id[bid] for bid in branch_ids], key=lambda p: p.id)
    if not branches:
        return {"skipped_missing": 1}

    # Title-case the cluster prefix. e.g. "acai luv" -> "Acai Luv".
    synth_name = " ".join(t.capitalize() for t in cluster["cluster_id"].split())

    if dry_run:
        # Don't actually create; report what we would do.
        summary = {"canonical_id": f"<synthesized:{synth_name!r}>",
                   "loser_ids": branch_ids, "discounts_moved": 0, "fields_copied": []}
        for branch in branches:
            summary["discounts_moved"] += Discount.objects.filter(place=branch).count()
        return summary

    # Use the first branch's metadata as the synthesized brand's seed values.
    seed = branches[0]
    canonical = Place(
        name=synth_name,
        category=seed.category or Category.RESTAURANT,
        area="",  # branches usually have empty area; leave for backfill loop
    )
    canonical.save()  # generates slug; collisions handled by Place.save() suffixing

    # Backfill seed fields into the freshly-created canonical.
    for field in COPY_FIELDS:
        sval = getattr(seed, field)
        if not _is_empty(sval) and _is_empty(getattr(canonical, field)):
            setattr(canonical, field, sval)
    canonical.save()

    summary = {"canonical_id": canonical.id, "loser_ids": branch_ids,
               "discounts_moved": 0, "fields_copied": [f"<seeded from {seed.id}>"]}

    for branch in branches:
        moved, copied = _merge_loser_into(canonical, branch, dry_run=False)
        summary["discounts_moved"] += moved
        summary["fields_copied"].extend(f"{f}<-{branch.id}" for f in copied)

    return summary


# Dispatch table: cluster kind -> merge function.
MERGERS = {
    "cross_source": _merge_cross_source,
    "brand_with_branches": _merge_brand_with_branches,
    "synthesizable_branches": _merge_synthesizable_branches,
}


class Command(BaseCommand):
    help = "Merge duplicate Places per data/place_duplicates_enriched.json."

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
        eligible = [
            c for c in clusters
            if c.get("auto_merge") and (c.get("confidence") == "high" or include_reviewed)
        ]
        self.stdout.write(f"loaded {len(clusters)} clusters; {len(eligible)} eligible for merge")

        # Gather all Place ids referenced — branches AND brand entries.
        place_ids: set[int] = set()
        for c in eligible:
            for p in c.get("places", []):
                if isinstance(p.get("id"), int):
                    place_ids.add(p["id"])
            for bid in (c.get("branch_ids") or []):
                place_ids.add(bid)
            if c.get("brand_id"):
                place_ids.add(c["brand_id"])
            if isinstance(c.get("suggested_canonical_id"), int):
                place_ids.add(c["suggested_canonical_id"])
        places_by_id = {p.id: p for p in Place.objects.filter(id__in=place_ids)}

        totals = {
            "by_kind": {k: 0 for k in MERGERS},
            "clusters_merged": 0, "discounts_moved": 0,
            "losers_unpublished": 0, "synthesized": 0, "skipped": 0,
        }

        for cluster in eligible:
            kind = cluster.get("kind", "cross_source")
            merger = MERGERS.get(kind)
            if merger is None:
                self.stdout.write(f"  SKIP {cluster['cluster_id']!r}: unknown kind {kind!r}")
                totals["skipped"] += 1
                continue

            self.stdout.write(
                f"\n[{cluster['cluster_id']!r}] kind={kind} (confidence={cluster['confidence']})"
            )
            try:
                with transaction.atomic():
                    summary = merger(cluster, places_by_id, dry_run=not apply, stdout=self.stdout)
                    if not apply:
                        transaction.set_rollback(True)
            except Exception as e:  # noqa: BLE001 - one bad cluster shouldn't kill the run
                self.stderr.write(f"  ERROR in {cluster['cluster_id']!r}: {e}")
                totals["skipped"] += 1
                continue

            if "skipped_missing" in summary:
                self.stdout.write(f"  SKIP: a Place id is missing in the DB")
                totals["skipped"] += 1
                continue

            totals["by_kind"][kind] += 1
            totals["clusters_merged"] += 1
            totals["discounts_moved"] += summary["discounts_moved"]
            totals["losers_unpublished"] += len(summary["loser_ids"])
            if kind == "synthesizable_branches":
                totals["synthesized"] += 1

            self.stdout.write(
                f"  canonical={summary['canonical_id']} "
                f"losers={len(summary['loser_ids'])} "
                f"discounts_moved={summary['discounts_moved']}"
            )

        self.stdout.write("\n--- Summary ---")
        for kind in MERGERS:
            self.stdout.write(f"  {kind:<24} clusters merged: {totals['by_kind'][kind]}")
        self.stdout.write(f"  total clusters merged:    {totals['clusters_merged']}")
        self.stdout.write(f"  losers unpublished:       {totals['losers_unpublished']}")
        self.stdout.write(f"  discounts re-pointed:     {totals['discounts_moved']}")
        self.stdout.write(f"  brand Places synthesized: {totals['synthesized']}")
        self.stdout.write(f"  clusters skipped:         {totals['skipped']}")
        if not apply:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes committed. Pass --apply to write."))
