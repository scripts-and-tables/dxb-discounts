"""Ingest enriched JSON from refresh-* skills into Place + Discount rows.

Each offer becomes its own Discount. Same place across sources collapses to
one Place via apps.places.matching.find_or_create_place. Idempotent — safe
to re-run on a schedule (uses stable per-source slugs and update_or_create).

Usage:
  python manage.py ingest_offers --source {entertainer,fazaa,playbook,all}
  python manage.py ingest_offers --source all --dry-run
  python manage.py ingest_offers --source playbook --limit 50

Inputs (produced by the refresh-* skills):
  data/entertainer_outlets_enriched.json
  data/fazaa_search_enriched.json
  data/playbook_search_enriched.json

The command never deletes anything. It upserts Discounts by stable slug
(e.g. 'entertainer-12345-67890-99'), so re-running with newer JSON updates
existing rows in place. Discounts no longer present in the source aren't
removed — handle that as a separate cleanup pass when you trust the source
diff is real (not a transient API blip).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.discounts.models import Discount, DiscountProgram, DiscountType
from apps.places.matching import find_or_create_place, prime_cache
from apps.places.models import Category, Place


ROOT = Path(__file__).resolve().parents[4]
DATA = ROOT / "data"


# ---------- helpers ---------------------------------------------------------


def _parse_iso_date(value) -> date | None:
    """Best-effort ISO parse to a date. Returns None for empty / unparseable."""
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    # Common shapes:
    #   2026-12-31T00:00:00+0400
    #   2026-06-02T00:00:00Z
    #   2026-12-31
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        # Python's fromisoformat handles +HH:MM, not +HHMM — pad if needed.
        if len(s) >= 5 and s[-5] in "+-" and s[-3] != ":":
            s = s[:-2] + ":" + s[-2:]
        return datetime.fromisoformat(s).date()
    except (ValueError, TypeError):
        return None


def _decimal(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _category_for(category_names: list[str] | None) -> str:
    """Map source-side category strings → our Place.category enum."""
    haystack = " ".join((c or "").lower() for c in (category_names or []))
    if any(k in haystack for k in ("hotel", "stay", "resort")):
        return Category.HOTEL
    if any(k in haystack for k in ("attraction", "entertain", "leisure", "park", "experience")):
        return Category.ATTRACTION
    if any(k in haystack for k in ("retail", "shop", "fashion", "wellness", "salon", "beauty", "spa")):
        return Category.RETAIL
    return Category.RESTAURANT


@dataclass
class IngestStats:
    source: str
    places_created: int = 0
    places_matched: int = 0
    discounts_created: int = 0
    discounts_updated: int = 0
    skipped: int = 0


# ---------- per-source ingestors -------------------------------------------


def _entertainer_place_name(merchant_name: str, outlet_name: str) -> str:
    """Build a human-readable Place name from Entertainer's two-field naming.

    - 'Color & Aroma' + 'Al Barsha' -> 'Color & Aroma — Al Barsha' (separate
      branches collapse to separate Places)
    - 'Go Thai - Al Wasl' (already includes brand) -> 'Go Thai - Al Wasl'
    """
    m = (merchant_name or "").strip()
    o = (outlet_name or "").strip()
    if not m:
        return o
    if not o:
        return m
    if m.lower() in o.lower():
        return o
    return f"{m} — {o}"


def ingest_entertainer(*, dry_run: bool, limit: int | None) -> IngestStats:
    stats = IngestStats(source="entertainer")
    path = DATA / "entertainer_outlets_enriched.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    if limit:
        rows = rows[:limit]
    for row in rows:
        merchant_id = row.get("merchant_id")
        outlet_id = row.get("outlet_id")
        if not merchant_id or not outlet_id:
            stats.skipped += 1
            continue
        merchant_name = row.get("merchant_name") or ""
        outlet_name = row.get("outlet_name") or ""
        coords = row.get("outlet_coordinates") or {}
        lat = coords.get("lat")
        lng = coords.get("lon")  # source uses 'lon', not 'lng'
        category = _category_for(row.get("merchant_categories_names"))
        place_name = _entertainer_place_name(merchant_name, outlet_name)
        if not place_name:
            stats.skipped += 1
            continue
        if dry_run:
            place, created = None, False  # placeholder
        else:
            place, created = find_or_create_place(
                name=place_name,
                lat=lat,
                lng=lng,
                category=category,
                defaults={},
            )
        if created:
            stats.places_created += 1
        else:
            stats.places_matched += 1

        # Walk all offer_sections.offers (Monthly Offers, hotel packages…)
        sections = row.get("offer_sections") or []
        for section in sections:
            for offer in section.get("offers") or []:
                offer_id = offer.get("offer_id")
                if not offer_id:
                    continue
                discount_slug = f"entertainer-{merchant_id}-{outlet_id}-{offer_id}"
                voucher_type = offer.get("voucher_type")
                is_pct = offer.get("is_percentage_offer")
                if voucher_type == 1:
                    dtype = DiscountType.BOGO
                elif voucher_type == 2 or is_pct:
                    dtype = DiscountType.PERCENTAGE
                else:
                    dtype = DiscountType.OTHER

                conditions = [c for c in (offer.get("conditions") or []) if c]
                tnc = offer.get("terms_and_conditions") or ""
                rules = offer.get("rules_of_use") or ""
                terms = "\n".join(p for p in [*conditions, tnc, rules] if p).strip()
                title = (offer.get("name") or "Entertainer Offer")[:200]
                description = (offer.get("offer_detail") or offer.get("details") or "").strip() or section.get("section_name", "")

                defaults = {
                    "place": place,
                    "title": title,
                    "discount_type": dtype,
                    "description": description,
                    "terms": terms,
                    "source_program": DiscountProgram.ENTERTAINER,
                    "is_members_only": True,
                    "is_active": True,
                    "valid_from": _parse_iso_date(offer.get("valid_from_date")),
                    "valid_until": _parse_iso_date(offer.get("validity_date")),
                }
                if dry_run:
                    stats.discounts_created += 1
                    continue
                _, was_created = Discount.objects.update_or_create(
                    slug=discount_slug, defaults=defaults,
                )
                if was_created:
                    stats.discounts_created += 1
                else:
                    stats.discounts_updated += 1
    return stats


def ingest_fazaa(*, dry_run: bool, limit: int | None) -> IngestStats:
    stats = IngestStats(source="fazaa")
    path = DATA / "fazaa_search_enriched.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    if limit:
        rows = rows[:limit]
    for row in rows:
        slug = row.get("slug")
        if not slug:
            stats.skipped += 1
            continue
        detail = row.get("detail") or {}
        if not detail:
            stats.skipped += 1
            continue
        partner_name = (
            (detail.get("partner") or {}).get("partnerName")
            or row.get("partnerName")
            or ""
        )
        # Source uses 'lon' on locations.
        locs = row.get("locations") or []
        first = locs[0] if locs else {}
        lat = first.get("lat") if isinstance(first, dict) else None
        lng = first.get("lon") if isinstance(first, dict) else None
        if lat == 0 and lng == 0:
            lat = lng = None
        ld_en = (detail.get("localData") or {}).get("en") or {}
        category_names = [c.get("name", "") for c in (detail.get("categories") or []) if isinstance(c, dict)]
        category = _category_for(category_names)
        place_name = partner_name.strip()
        if not place_name:
            stats.skipped += 1
            continue
        if dry_run:
            place, created = None, False
        else:
            place, created = find_or_create_place(
                name=place_name, lat=lat, lng=lng, category=category,
                defaults={"website": (detail.get("partner") or {}).get("partnerLink", "")},
            )
        if created:
            stats.places_created += 1
        else:
            stats.places_matched += 1

        # discount_type from detail.discountType
        discount_str = detail.get("discount")
        dtype_raw = (detail.get("discountType") or "").upper()
        percentage = None
        fixed = None
        if dtype_raw == "PERCENTAGE":
            dtype = DiscountType.PERCENTAGE
            try:
                percentage = int(float(str(discount_str))) if discount_str not in (None, "") else None
            except (ValueError, TypeError):
                percentage = None
        elif dtype_raw == "FIXED":
            dtype = DiscountType.FIXED_PRICE
            fixed = _decimal(discount_str)
        else:
            dtype = DiscountType.OTHER

        title = (ld_en.get("title") or row.get("title") or "Fazaa Offer")[:200]
        description = (ld_en.get("shortDescription") or row.get("subTitle") or "").strip()
        terms = (ld_en.get("description") or "").strip()
        external_url = (detail.get("partner") or {}).get("partnerLink", "") or ""

        defaults = {
            "place": place,
            "title": title,
            "discount_type": dtype,
            "percentage": percentage,
            "fixed_price_aed": fixed,
            "description": description,
            "terms": terms,
            "external_url": external_url[:500],
            "source_program": DiscountProgram.FAZAA,
            "is_members_only": False,
            "is_active": True,
            "valid_until": _parse_iso_date(detail.get("offerExpiry")),
        }
        if dry_run:
            stats.discounts_created += 1
            continue
        _, was_created = Discount.objects.update_or_create(
            slug=f"fazaa-{slug}", defaults=defaults,
        )
        if was_created:
            stats.discounts_created += 1
        else:
            stats.discounts_updated += 1
    return stats


def ingest_playbook(*, dry_run: bool, limit: int | None) -> IngestStats:
    stats = IngestStats(source="playbook")
    path = DATA / "playbook_search_enriched.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    if limit:
        rows = rows[:limit]
    for row in rows:
        venue_id = row.get("Id")
        if not venue_id:
            stats.skipped += 1
            continue
        detail = row.get("detail") or {}
        if not detail or detail.get("StatusCode"):
            stats.skipped += 1
            continue
        place_name = (row.get("Name") or "").strip()
        if not place_name:
            stats.skipped += 1
            continue
        lat = row.get("Lat")
        lng = row.get("Lng")
        area = row.get("AreaName") or ""
        building = row.get("BuildingName") or ""
        address = " · ".join(p for p in [building, area] if p)
        if dry_run:
            place, created = None, False
        else:
            place, created = find_or_create_place(
                name=place_name, lat=lat, lng=lng, area=area,
                category=Category.RESTAURANT,
                defaults={
                    "address": address,
                    "phone": detail.get("Phone", ""),
                    "website": detail.get("WebsiteUrl", "")[:200] if detail.get("WebsiteUrl") else "",
                    "description": detail.get("About", ""),
                },
            )
        if created:
            stats.places_created += 1
        else:
            stats.places_matched += 1

        external_url = f"https://www.my-playbook.com/venue/{venue_id}/{slugify(place_name)}"
        for hl in detail.get("Highlights") or []:
            hl_id = hl.get("Id")
            if not hl_id:
                continue
            title = (hl.get("Name") or "Playbook Offer")[:200]
            general = (hl.get("GeneralDescription") or "").strip()
            detailed = (hl.get("DetailedDescription") or "").strip()
            description = "\n\n".join(p for p in [general, detailed] if p)
            defaults = {
                "place": place,
                "title": title,
                "discount_type": DiscountType.OTHER,
                "description": description,
                "terms": "",
                "external_url": external_url[:500],
                "source_program": DiscountProgram.PLAYBOOK,
                "is_members_only": False,
                "is_active": True,
            }
            if dry_run:
                stats.discounts_created += 1
                continue
            _, was_created = Discount.objects.update_or_create(
                slug=f"playbook-{venue_id}-{hl_id}", defaults=defaults,
            )
            if was_created:
                stats.discounts_created += 1
            else:
                stats.discounts_updated += 1
    return stats


# ---------- backfill --------------------------------------------------------


def backfill_existing_place_coords() -> int:
    """Walk every Place with no lat/lng and try to fill from any source's
    enriched JSON whose normalized name matches by slug. Touch only empty
    rows — never overwrite curator-set coords."""
    from apps.places.matching import normalize_name
    candidates: list[Place] = list(Place.objects.filter(lat__isnull=True))
    if not candidates:
        return 0
    name_to_coords: dict[str, tuple[float, float]] = {}
    # Pull coords from every source we have
    for src_path, name_keys, lat_path, lng_path in [
        (DATA / "playbook_search_enriched.json", ["Name"], "Lat", "Lng"),
        (DATA / "entertainer_outlets_enriched.json",
         ["merchant_name", "outlet_name"], None, None),
        (DATA / "fazaa_search_enriched.json", ["partnerName"], None, None),
    ]:
        if not src_path.exists():
            continue
        try:
            data = json.loads(src_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for r in data:
            if "playbook" in src_path.name:
                lat, lng = r.get("Lat"), r.get("Lng")
                key = normalize_name(r.get("Name") or "")
            elif "entertainer" in src_path.name:
                coords = r.get("outlet_coordinates") or {}
                lat, lng = coords.get("lat"), coords.get("lon")
                m, o = r.get("merchant_name") or "", r.get("outlet_name") or ""
                key = normalize_name(_entertainer_place_name(m, o))
            else:
                locs = r.get("locations") or []
                first = locs[0] if locs else {}
                lat = first.get("lat") if isinstance(first, dict) else None
                lng = first.get("lon") if isinstance(first, dict) else None
                key = normalize_name(r.get("partnerName") or "")
            if lat is None or lng is None or (lat == 0 and lng == 0) or not key:
                continue
            name_to_coords.setdefault(key, (float(lat), float(lng)))
    filled = 0
    for p in candidates:
        key = normalize_name(p.name)
        if key in name_to_coords:
            lat, lng = name_to_coords[key]
            p.lat = Decimal(str(lat))
            p.lng = Decimal(str(lng))
            p.save(update_fields=["lat", "lng"])
            filled += 1
    return filled


# ---------- command ---------------------------------------------------------


SOURCE_FNS = {
    "entertainer": ingest_entertainer,
    "fazaa": ingest_fazaa,
    "playbook": ingest_playbook,
}


class Command(BaseCommand):
    help = "Ingest enriched JSON from refresh-* skills into Place + Discount."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source", choices=["all", *SOURCE_FNS.keys()], default="all",
            help="Which source to ingest (default: all)",
        )
        parser.add_argument("--dry-run", action="store_true",
                            help="Don't write to the DB, just count.")
        parser.add_argument("--limit", type=int, default=None,
                            help="Process only the first N rows per source (for smoke tests).")
        parser.add_argument("--skip-backfill", action="store_true",
                            help="Skip the lat/lng backfill on existing Places.")

    def handle(self, *args, dry_run: bool, source: str, limit: int | None,
               skip_backfill: bool, **kwargs):
        if not skip_backfill and not dry_run:
            self.stdout.write("Backfilling lat/lng on existing Places...")
            n = backfill_existing_place_coords()
            self.stdout.write(self.style.SUCCESS(f"  filled {n} Places."))

        # Prime the matcher cache once after backfill.
        prime_cache()

        sources = list(SOURCE_FNS.keys()) if source == "all" else [source]
        all_stats: list[IngestStats] = []
        for src in sources:
            self.stdout.write(f"\nIngesting {src}...")
            fn = SOURCE_FNS[src]
            with transaction.atomic():
                stats = fn(dry_run=dry_run, limit=limit)
                if dry_run:
                    transaction.set_rollback(True)
            all_stats.append(stats)
            self.stdout.write(self.style.SUCCESS(
                f"  {src}: places created={stats.places_created} "
                f"matched={stats.places_matched} | "
                f"discounts created={stats.discounts_created} "
                f"updated={stats.discounts_updated} | skipped={stats.skipped}"
            ))

        self.stdout.write("\n--- Summary ---")
        tot_pc = sum(s.places_created for s in all_stats)
        tot_pm = sum(s.places_matched for s in all_stats)
        tot_dc = sum(s.discounts_created for s in all_stats)
        tot_du = sum(s.discounts_updated for s in all_stats)
        self.stdout.write(f"Places: {tot_pc} created, {tot_pm} matched (across sources)")
        self.stdout.write(f"Discounts: {tot_dc} created, {tot_du} updated")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes committed."))
