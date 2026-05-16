"""Ingest enriched JSON from refresh-* skills into Place + Discount rows.

Each offer becomes its own Discount. Same place across sources collapses to
one Place via apps.places.matching.find_or_create_place. Idempotent — safe
to re-run on a schedule (uses stable per-source slugs and update_or_create).

Usage:
  python manage.py ingest_offers --source {entertainer,fazaa,all}
  python manage.py ingest_offers --source all --dry-run
  python manage.py ingest_offers --source fazaa --limit 50

Inputs (produced by the refresh-* skills):
  data/entertainer_outlets_enriched.json
  data/fazaa_search_enriched.json
  data/playbook_search_enriched.json  (read by backfill only; not ingested
                                       as discounts — see note below)

The command never deletes anything. It upserts Discounts by stable slug
(e.g. 'entertainer-12345-67890-99'), so re-running with newer JSON updates
existing rows in place.

Discounts no longer present in the source stay around with their existing
`is_active` value unless you pass `--deactivate-missing`, which marks them
`is_active=False` once the source-side payload is trusted. That flag is
scoped per source (filters by `source_program` AND slug prefix) and refuses
to run with `--limit` (a partial scan would wrongly deactivate everything
past the limit).

`is_active` is intentionally not in the upsert defaults: new rows get the
model default of True, existing rows keep whatever state they had — so
curator-deactivated offers (and offers turned off on a prior
`--deactivate-missing` run) survive an ingest.
"""
from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

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


def _clean_website(url: str | None) -> str:
    """Fit a URL into Place.website's URLField(max_length=200).

    Long URLs (tracking-laden marketing links from Fazaa partnerLink, etc.)
    blow up under Postgres' strict varchar check even though SQLite tolerates
    them. When the URL is too long, fall back to just its origin
    (scheme://host/), which is a valid URL and usually points at the brand
    homepage. As a last resort, return "" rather than silently truncating
    to a broken path.
    """
    if not url:
        return ""
    url = url.strip()
    if len(url) <= 200:
        return url
    try:
        p = urllib.parse.urlparse(url)
        if p.netloc:
            origin = f"{p.scheme or 'https'}://{p.netloc}/"
            return origin if len(origin) <= 200 else ""
    except ValueError:
        pass
    return ""


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
    discounts_deactivated: int = 0  # set by --deactivate-missing post-pass
    skipped: int = 0
    slugs_seen: set[str] = field(default_factory=set)


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
                stats.slugs_seen.add(discount_slug)
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
                    # is_active is intentionally omitted: new rows get True via
                    # the model default, existing rows keep their value (so a
                    # curator-deactivated row, or one that --deactivate-missing
                    # turned off on a prior run, stays off).
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
                defaults={"website": _clean_website((detail.get("partner") or {}).get("partnerLink"))},
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
            # is_active intentionally omitted — see entertainer block above.
            "valid_until": _parse_iso_date(detail.get("offerExpiry")),
        }
        discount_slug = f"fazaa-{slug}"
        stats.slugs_seen.add(discount_slug)
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


def ingest_adcb_touchpoints(*, dry_run: bool, limit: int | None) -> IngestStats:
    """Ingest ADCB TouchPoints partner offers from
    data/adcb_offers_enriched.json (produced by the refresh-adcb-touchpoints
    skill).

    Each ADCB API record becomes one Discount keyed by `adcb-{offer-uuid}`.
    The Place is matched/created from the offer's brand_name (+ coords from
    the API). Many offers share a brand (e.g. Mall of the Emirates has 100+
    offers) — find_or_create_place collapses them onto a single Place via
    name+coords matching.

    The discount-% is parsed best-effort by parse_adcb_offers.py; offers
    whose title doesn't match a clean pattern fall through as
    discount_type=OTHER with the raw title preserved.
    """
    stats = IngestStats(source="adcb_touchpoints")
    path = DATA / "adcb_offers_enriched.json"
    if not path.exists():
        return stats

    rows = json.loads(path.read_text(encoding="utf-8"))
    if limit:
        rows = rows[:limit]

    type_map = {
        "percentage": DiscountType.PERCENTAGE,
        "fixed_price": DiscountType.FIXED_PRICE,
        "bogo": DiscountType.BOGO,
        "other": DiscountType.OTHER,
    }

    for row in rows:
        offer_id = row.get("id")
        brand_name = (row.get("brand_name") or "").strip()
        title = (row.get("title") or "").strip()
        if not offer_id or not brand_name or not title:
            stats.skipped += 1
            continue

        lat = row.get("lat")
        lng = row.get("lng")
        if lat == 0 and lng == 0:
            lat = lng = None  # treat (0,0) as "no coords" like Fazaa

        category_hint = (row.get("category") or "").lower()
        category = _category_for([category_hint])

        place_defaults = {
            "logo_url_override": (row.get("brand_logo") or row.get("merchant_logo") or "")[:500],
        }
        if dry_run:
            place, created = None, False
        else:
            place, created = find_or_create_place(
                name=brand_name,
                lat=lat, lng=lng,
                category=category,
                defaults={k: v for k, v in place_defaults.items() if v},
            )
        if created:
            stats.places_created += 1
        else:
            stats.places_matched += 1

        discount_slug = f"adcb-{offer_id}"
        stats.slugs_seen.add(discount_slug)
        dtype = type_map.get(row.get("discount_type"), DiscountType.OTHER)

        # ADCB's SPA doesn't have per-offer permalinks — offer detail opens
        # in a client-side modal. The closest stable public URL is the
        # `offers list` route with the brand pre-loaded into the `keywords`
        # query param, which the SPA picks up on init and uses to filter
        # the catalogue.
        external_url = (
            "https://offers.adcb.com/offer/websites/personal/touchpoints-offers/list"
            f"?keywords={urllib.parse.quote(brand_name)}"
        )[:500]

        defaults = {
            "place": place,
            "title": title[:200],
            "discount_type": dtype,
            "percentage": row.get("percentage"),
            "fixed_price_aed": _decimal(row.get("fixed_price_aed")),
            "description": (row.get("description") or title)[:2000],
            "external_url": external_url,
            "source_program": DiscountProgram.ADCB_TOUCHPOINTS,
            "is_members_only": False,
            # is_active intentionally omitted (curator overrides survive).
            "valid_until": _parse_iso_date(row.get("end_time")),
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


def ingest_atlantis_circle(*, dry_run: bool, limit: int | None) -> IngestStats:
    """Ingest the 20 Atlantis Dubai dining venues from
    data/atlantis_circle_enriched.json (produced by the refresh-atlantis-circle
    skill).

    Each venue becomes one Discount at the Blue (free) tier — currently 15% off.
    Tier ladder is described in the discount's `terms` so users know about the
    Silver/Gold/Black upgrades. Slug pattern matches migration
    0026_atlantis_circle_venues.py: `atlantis-circle-{place-slug}`.
    """
    stats = IngestStats(source="atlantis_circle")
    path = DATA / "atlantis_circle_enriched.json"
    if not path.exists():
        return stats  # skill hasn't been run yet — caller decides what to do

    rows = json.loads(path.read_text(encoding="utf-8"))
    tiers_path = DATA / "atlantis_circle_tiers.json"
    tiers_meta = (
        json.loads(tiers_path.read_text(encoding="utf-8"))
        if tiers_path.exists() else {}
    )
    tier_lines = " / ".join(
        f"{t['name']} {t['percentage']}%" for t in (tiers_meta.get("tiers") or [])
    ) or "Blue 15% / Silver 20% / Gold 25% / Black 30%"

    if limit:
        rows = rows[:limit]
    for row in rows:
        slug = row.get("slug")
        if not slug:
            stats.skipped += 1
            continue
        place_name = row.get("name") or slug.replace("-", " ").title()
        category = Category.RESTAURANT
        lat = row.get("lat")
        lng = row.get("lng")

        place_defaults = {
            "address": row.get("address") or "",
            "website": row.get("external_url") or "",
            "description": row.get("cuisine_blurb") or "",
            "phone": row.get("phone") or "",
            # Per-venue logo from schema.org Restaurant JSON-LD (Kerzner CDN).
            # Without this, every Atlantis venue falls back to the same
            # icon.horse(atlantis.com) generic resort logo because they all
            # share Place.website = atlantis.com/dubai/dining/...
            "logo_url_override": (row.get("logo_url") or "")[:500],
        }

        # Atlantis slugs are authoritative (hard-coded in scripts/parse_atlantis_circle.py
        # to match migration 0026_atlantis_circle_venues.py), so skip the
        # name-based matcher and look up by slug directly. This avoids
        # accidentally creating a duplicate Place when the seed row exists
        # without lat/lng (find_or_create_place's name+coords match needs
        # both sides to have coords; the seed doesn't).
        if dry_run:
            place, created = None, False
        else:
            place = Place.objects.filter(slug=slug).first()
            if place is None:
                place, created = find_or_create_place(
                    name=place_name, lat=lat, lng=lng,
                    category=category,
                    defaults={**place_defaults, "area": "Palm Jumeirah"},
                )
            else:
                created = False
                changed = False
                # Backfill empty fields on the existing Place from fresh source data.
                # Never overwrite curator-set values.
                if place.lat is None and lat is not None:
                    place.lat = Decimal(str(lat)); changed = True
                if place.lng is None and lng is not None:
                    place.lng = Decimal(str(lng)); changed = True
                for k, v in place_defaults.items():
                    if v and not getattr(place, k, None):
                        setattr(place, k, v); changed = True
                if changed:
                    place.save()
        if created:
            stats.places_created += 1
        else:
            stats.places_matched += 1

        discount_slug = f"atlantis-circle-{slug}"
        stats.slugs_seen.add(discount_slug)
        blue_pct = row.get("tier_percentages", {}).get("blue", 15)
        title = f"{place_name} — {blue_pct}% off with Atlantis Circle (Blue, free)"
        description = (
            f"{row.get('cuisine_blurb', '')}\n\n"
            f"Atlantis Circle members get tiered F&B discounts at all Atlantis "
            f"Dubai dining venues ({tier_lines}). The Blue tier is free; higher "
            f"tiers unlock as your rolling 12-month spend grows. Sign up at "
            f"https://www.atlantis.com/dubai/membership/atlantis-circle."
        ).strip()
        terms = (
            "Discount applies to the food & beverage bill, excluding alcohol "
            "and service charge unless stated. Members must present a valid "
            "Atlantis Circle digital card before settling. Tier % is set by "
            "rolling 12-month dining spend at Atlantis Dubai venues. See "
            "atlantis.com/dubai/membership/atlantis-circle for full terms, "
            "exclusions and tier qualifying rules."
        )
        defaults = {
            "place": place,
            "title": title[:200],
            "discount_type": DiscountType.PERCENTAGE,
            "percentage": blue_pct,
            "description": description,
            "terms": terms,
            "external_url": (row.get("external_url") or "")[:500],
            "source_program": DiscountProgram.ATLANTIS_CIRCLE,
            "is_members_only": False,
            # is_active intentionally omitted (curator-deactivated rows survive).
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

        # Explicit pause handling: if the source flags the venue as not
        # operational, deactivate. find_or_create_place / update_or_create
        # never touch is_active, so this is the only path that turns offers
        # off when the source signals so.
        if not row.get("is_operational", True):
            Discount.objects.filter(slug=discount_slug).update(is_active=False)
    return stats


def ingest_playbook(*, dry_run: bool, limit: int | None) -> IngestStats:
    """No-op kept for historical migration compatibility.

    Playbook (my-playbook.com) turned out to be a venue-discovery app, not
    a discount program — its "Highlights" were marketing events (Ladies
    Night, Afternoon Tea, …), not offers. The real ingest function was
    removed; migration 0015_remove_playbook_data deleted all rows it had
    created. We keep this stub so migration 0012 (already applied on prod)
    still runs cleanly on a fresh-from-scratch dev DB.

    data/playbook_search_enriched.json is still kept and used by
    backfill_existing_place_coords() and the refresh-icons skill for
    venue logos/website hints.
    """
    return IngestStats(source="playbook")


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
    "atlantis_circle": ingest_atlantis_circle,
    "adcb_touchpoints": ingest_adcb_touchpoints,
    "playbook": ingest_playbook,  # no-op; kept so migration 0012 still works
}

# Sources actually included by `--source all`. Playbook is dropped because
# its ingest is a no-op (the program isn't really a discount program).
ALL_SOURCES = ["entertainer", "fazaa", "atlantis_circle", "adcb_touchpoints"]

# (DiscountProgram value, slug prefix) per source. The prefix is used by
# --deactivate-missing to scope the diff query — anything with the right
# source_program but a non-matching slug (e.g. legacy `ent-` rows that
# pre-date the per-offer slug scheme) is left alone.
SOURCE_TO_PROGRAM = {
    "entertainer": (DiscountProgram.ENTERTAINER, "entertainer-"),
    "fazaa": (DiscountProgram.FAZAA, "fazaa-"),
    "atlantis_circle": (DiscountProgram.ATLANTIS_CIRCLE, "atlantis-circle-"),
    "adcb_touchpoints": (DiscountProgram.ADCB_TOUCHPOINTS, "adcb-"),
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
        parser.add_argument(
            "--deactivate-missing", action="store_true",
            help=(
                "After each source's ingest, mark `is_active=False` on Discounts "
                "with this source_program whose slug wasn't seen in the current "
                "payload. Refuses to run when --limit is set (the slug set would "
                "be partial). Pairs with --dry-run to preview the count."
            ),
        )

    def handle(self, *args, dry_run: bool, source: str, limit: int | None,
               skip_backfill: bool, deactivate_missing: bool, **kwargs):
        if deactivate_missing and limit is not None:
            self.stderr.write(self.style.ERROR(
                "--deactivate-missing cannot be combined with --limit "
                "(the slug set would be partial and would wrongly deactivate "
                "offers that weren't visited)."
            ))
            return
        if not skip_backfill and not dry_run:
            self.stdout.write("Backfilling lat/lng on existing Places...")
            n = backfill_existing_place_coords()
            self.stdout.write(self.style.SUCCESS(f"  filled {n} Places."))

        # Prime the matcher cache once after backfill.
        prime_cache()

        sources = list(ALL_SOURCES) if source == "all" else [source]
        all_stats: list[IngestStats] = []
        for src in sources:
            self.stdout.write(f"\nIngesting {src}...")
            fn = SOURCE_FNS[src]
            with transaction.atomic():
                stats = fn(dry_run=dry_run, limit=limit)
                if deactivate_missing and src in SOURCE_TO_PROGRAM:
                    program, prefix = SOURCE_TO_PROGRAM[src]
                    missing_qs = Discount.objects.filter(
                        source_program=program,
                        slug__startswith=prefix,
                        is_active=True,
                    ).exclude(slug__in=stats.slugs_seen)
                    if dry_run:
                        stats.discounts_deactivated = missing_qs.count()
                    else:
                        stats.discounts_deactivated = missing_qs.update(is_active=False)
                if dry_run:
                    transaction.set_rollback(True)
            all_stats.append(stats)
            deact_part = (
                f" | deactivated={stats.discounts_deactivated}"
                if deactivate_missing else ""
            )
            self.stdout.write(self.style.SUCCESS(
                f"  {src}: places created={stats.places_created} "
                f"matched={stats.places_matched} | "
                f"discounts created={stats.discounts_created} "
                f"updated={stats.discounts_updated}{deact_part} | "
                f"skipped={stats.skipped}"
            ))

        self.stdout.write("\n--- Summary ---")
        tot_pc = sum(s.places_created for s in all_stats)
        tot_pm = sum(s.places_matched for s in all_stats)
        tot_dc = sum(s.discounts_created for s in all_stats)
        tot_du = sum(s.discounts_updated for s in all_stats)
        tot_dd = sum(s.discounts_deactivated for s in all_stats)
        self.stdout.write(f"Places: {tot_pc} created, {tot_pm} matched (across sources)")
        self.stdout.write(f"Discounts: {tot_dc} created, {tot_du} updated")
        if deactivate_missing:
            self.stdout.write(f"Discounts deactivated (missing from source): {tot_dd}")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes committed."))
