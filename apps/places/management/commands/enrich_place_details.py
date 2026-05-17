"""Apply resolved Place details from data/place_details_enriched.json.

Reads the enriched JSON (produced by `scripts/resolve_place_details.py`)
and fills empty fields on matching Place rows. Never overwrites
curator-set values — only fills when the existing field is empty.

Dry-run by default. Pass --apply to actually mutate the DB.

Per-source override flags let you ingest selectively, e.g. to apply
website-jsonld fills but skip osm-overpass during a quality audit:

    python manage.py enrich_place_details --apply --skip-source osm-overpass

Each field's `source` tag (e.g. "website-jsonld", "osm-overpass") drives
the filter.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.places.models import Place


SRC = Path(__file__).resolve().parents[4] / "data" / "place_details_enriched.json"

# Place model max_lengths (cross-checked against apps/places/models.py)
FIELD_MAX = {
    "description": None,     # TextField — no max
    "phone": 40,
    "address": None,         # TextField
    "website": 200,
}


def _empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


class Command(BaseCommand):
    help = "Fill empty description/phone/address/website/lat/lng from data/place_details_enriched.json."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="actually write to the DB (default is dry-run)")
        parser.add_argument(
            "--skip-source", action="append", default=[],
            help="ignore fields tagged with this source (repeatable). "
                 "Sources include: website-jsonld, osm-overpass.",
        )
        parser.add_argument(
            "--only-fields", action="append", default=[],
            help="restrict to these field names (repeatable). "
                 "Without this flag, every populated field in the enriched JSON "
                 "is considered. Valid: description, phone, address, website, lat, lng.",
        )

    def handle(self, *args, apply: bool, skip_source: list[str],
               only_fields: list[str], **kwargs):
        if not SRC.exists():
            self.stderr.write(self.style.ERROR(
                f"missing {SRC.relative_to(Path.cwd())} — "
                "run scripts/resolve_place_details.py first."
            ))
            return

        rows = json.loads(SRC.read_text(encoding="utf-8"))
        self.stdout.write(f"loaded {len(rows)} enriched rows")
        if skip_source:
            self.stdout.write(self.style.WARNING(
                f"  ignoring source(s): {', '.join(skip_source)}"
            ))
        if only_fields:
            self.stdout.write(self.style.WARNING(
                f"  restricted to field(s): {', '.join(only_fields)}"
            ))

        fillable_fields = ("description", "phone", "address", "website", "lat", "lng")
        if only_fields:
            invalid = set(only_fields) - set(fillable_fields)
            if invalid:
                self.stderr.write(self.style.ERROR(f"unknown --only-fields: {invalid}"))
                return
            fillable_fields = tuple(f for f in fillable_fields if f in only_fields)

        # Counters
        per_field = {f: {"would_fill": 0, "skipped_already_set": 0,
                         "skipped_by_source": 0} for f in fillable_fields}
        rows_touched = 0
        place_not_found = 0

        with transaction.atomic():
            for r in rows:
                pid = r.get("id")
                try:
                    place = Place.objects.get(pk=pid)
                except Place.DoesNotExist:
                    place_not_found += 1
                    continue

                fields_to_set: dict[str, object] = {}
                for field in fillable_fields:
                    spec = r.get(field)
                    if not isinstance(spec, dict):
                        continue
                    if spec.get("source") in skip_source:
                        per_field[field]["skipped_by_source"] += 1
                        continue
                    current = getattr(place, field)
                    if not _empty(current):
                        per_field[field]["skipped_already_set"] += 1
                        continue
                    value = spec.get("value")
                    if value is None or (isinstance(value, str) and not value.strip()):
                        continue
                    # Truncate strings to model max_length
                    if isinstance(value, str):
                        max_len = FIELD_MAX.get(field)
                        if max_len:
                            value = value.strip()[:max_len]
                        else:
                            value = value.strip()
                    elif field in ("lat", "lng"):
                        try:
                            value = Decimal(str(value))
                        except Exception:  # noqa: BLE001
                            continue
                    fields_to_set[field] = value
                    per_field[field]["would_fill"] += 1

                if fields_to_set:
                    rows_touched += 1
                    if apply:
                        for k, v in fields_to_set.items():
                            setattr(place, k, v)
                        place.save(update_fields=list(fields_to_set.keys()))

            if not apply:
                transaction.set_rollback(True)

        self.stdout.write("\n--- Per-field summary ---")
        for field, counts in per_field.items():
            self.stdout.write(
                f"  {field:11s} would_fill={counts['would_fill']:5d}  "
                f"already_set={counts['skipped_already_set']:5d}  "
                f"src_skipped={counts['skipped_by_source']:5d}"
            )
        self.stdout.write(f"\nrows touched: {rows_touched}")
        if place_not_found:
            self.stdout.write(self.style.WARNING(
                f"  place_not_found: {place_not_found} (stale id in enriched JSON)"
            ))
        if not apply:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes committed. Pass --apply to write."))
