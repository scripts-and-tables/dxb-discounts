"""One-shot cleanup of legacy hand-rolled Entertainer Discount rows.

Migrations 0015–0017 created one generic Discount per venue with slug
`ent-{place_slug}` and title "Buy One Get One Free at <name> via The
Entertainer". The new ingest (`ingest_offers --source entertainer`) creates
one Discount per actual offer with slug `entertainer-{merchant_id}-{outlet_id}-{offer_id}`,
attached to a Place row whose name typically includes the outlet branch
(e.g. "Karma Kafé — Al Barsha"). Because the matcher couldn't connect the
old brand-name Place ("Karma Kafé") to the new branch-named Place, the new
specific discounts landed on duplicate Place rows — and users browsing the
old URL still saw only the generic offer.

This command:
  1. Where the SAME Place has both old + new Entertainer discounts → deletes
     the redundant old generic.
  2. Where only the old generic exists, tries to find a UNIQUE matching new
     Place by token-prefix on normalized names. If found, moves all
     entertainer-* discounts onto the old Place (preserving its slug/URL),
     fills any empty fields from the duplicate, deletes the duplicate, and
     deletes the old generic.
  3. Ambiguous (multi-branch brand) and no-match cases are left alone — the
     old generic survives as a brand-level fallback discount.

Usage:
  python manage.py consolidate_legacy_offers --dry-run   # inspect
  python manage.py consolidate_legacy_offers             # execute

Other source programs do NOT need this cleanup: Fazaa migrations and the
Fazaa ingest share the same `fazaa-{slug}` namespace (already merged via
update_or_create); Supper Club / Elite Club / Atlantis are hand-curated with
no automated ingest target.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.discounts.models import Discount
from apps.places.matching import normalize_name
from apps.places.models import Place


_OLD_PREFIX = "ent-"
_NEW_PREFIX = "entertainer-"


class Command(BaseCommand):
    help = "Consolidate legacy Entertainer generic discounts into the per-offer rows."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Don't write to the DB, just count.")

    def handle(self, *args, dry_run: bool, **kwargs):
        deleted_dual = 0
        merged = 0
        moved_discounts = 0
        deleted_target_places = 0
        skipped_ambiguous = 0
        skipped_no_match = 0

        # Cache of (id, name, normalized_name) for every Place that has at least
        # one new entertainer-* discount. Built once to avoid re-querying.
        new_place_rows = list(
            Place.objects
            .filter(discounts__slug__startswith=_NEW_PREFIX)
            .distinct()
            .values("id", "name")
        )
        new_index: list[tuple[int, str]] = [
            (r["id"], normalize_name(r["name"])) for r in new_place_rows
        ]

        with transaction.atomic():
            old_qs = (
                Discount.objects
                .filter(slug__startswith=_OLD_PREFIX, source_program="entertainer")
                .select_related("place")
                .order_by("id")
            )
            for d in old_qs.iterator():
                place = d.place

                # Case 1: same Place already has new specifics → delete old.
                if Discount.objects.filter(
                    place=place, slug__startswith=_NEW_PREFIX,
                ).exists():
                    d.delete()
                    deleted_dual += 1
                    continue

                old_norm = normalize_name(place.name)
                if not old_norm:
                    skipped_no_match += 1
                    continue

                # Case 2: try to find a unique merge candidate among the new places.
                matches = [
                    (pid, cname) for pid, cname in new_index
                    if pid != place.pk and cname and (
                        cname == old_norm
                        or cname.startswith(old_norm + " ")
                        or old_norm.startswith(cname + " ")
                    )
                ]

                if len(matches) == 1:
                    target_id, _ = matches[0]
                    target = Place.objects.get(pk=target_id)
                    # Move all entertainer-* discounts onto the old Place.
                    n_moved = Discount.objects.filter(
                        place=target, slug__startswith=_NEW_PREFIX,
                    ).update(place=place)
                    moved_discounts += n_moved

                    # Inherit any fields that were empty on the old place.
                    changed = False
                    for field in ("address", "phone", "website", "description"):
                        if not getattr(place, field) and getattr(target, field):
                            setattr(place, field, getattr(target, field))
                            changed = True
                    if place.lat is None and target.lat is not None:
                        place.lat, place.lng = target.lat, target.lng
                        changed = True
                    if changed:
                        place.save()

                    d.delete()
                    if not Discount.objects.filter(place=target).exists():
                        target.delete()
                        deleted_target_places += 1
                        # Drop the target from the in-memory index too so we
                        # don't pick it again for a later old discount.
                        new_index = [r for r in new_index if r[0] != target_id]
                    merged += 1
                elif len(matches) > 1:
                    skipped_ambiguous += 1
                else:
                    skipped_no_match += 1

            if dry_run:
                transaction.set_rollback(True)

        # --- Summary ---
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Consolidation summary"))
        self.stdout.write(f"  deleted_dual (same place had both): {deleted_dual}")
        self.stdout.write(f"  merged (old place absorbed new):    {merged}")
        self.stdout.write(f"  discounts moved to old places:      {moved_discounts}")
        self.stdout.write(f"  empty new places deleted:           {deleted_target_places}")
        self.stdout.write(f"  skipped — ambiguous (multi-branch): {skipped_ambiguous}")
        self.stdout.write(f"  skipped — no match in new ingest:   {skipped_no_match}")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes committed."))
