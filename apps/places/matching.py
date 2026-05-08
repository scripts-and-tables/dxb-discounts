"""Cross-source place deduplication.

When the same venue (e.g. "Giordano's Dubai Mall") appears in Entertainer,
Fazaa, AND Playbook, we want one Place row with multiple Discounts attached
— not three Place rows with one Discount each. This module is the matcher.

Strategy:
1. Exact slug lookup (cheap, catches re-runs)
2. Normalized-name match within ~150m haversine — handles "Giordano's" vs
   "Giordano" vs "GIORDANO Dubai Mall" + small GPS variance
3. Else create a fresh Place

Distance check uses pure-Python haversine; no PostGIS dependency.
"""
import math
import re
from decimal import Decimal

from django.db.models import Q
from django.utils.text import slugify

from .models import Category, Place


_PUNCTUATION_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")
# Words that don't help distinguish places — drop them when normalizing.
# "the" / "by" / "at" are stopwords; the rest are venue-type suffixes that
# different sources include or omit inconsistently ("Karma Kafé" vs "Karma").
_STOPWORDS = {
    "the", "a", "an", "by", "at", "of", "and",
    "restaurant", "restaurants", "cafe", "café", "kafe", "kafé", "bar", "lounge",
    "kitchen", "grill", "house", "club", "dubai", "uae", "emirates",
}


def normalize_name(name: str) -> str:
    """Lowercase, strip punctuation, drop stopwords/venue-types, collapse whitespace.

    Examples:
      'Karma Kafé by Buddha-Bar' -> 'karma buddha'
      "GIORDANO's Dubai Mall"    -> 'giordano mall'
      'The Sum of Us Café'       -> 'sum us'
    """
    if not name:
        return ""
    n = name.lower()
    n = _PUNCTUATION_RE.sub(" ", n)
    n = _WHITESPACE_RE.sub(" ", n).strip()
    tokens = [t for t in n.split() if t and t not in _STOPWORDS]
    return " ".join(tokens)


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres between two (lat, lng) points."""
    R = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# Module-level cache of (id, normalized_name, lat, lng) for the Dubai bbox.
# The ingest command can preload this once per source pass via prime_cache().
_NAME_CACHE: list[tuple[int, str, float | None, float | None]] | None = None


def prime_cache() -> None:
    """Load every published Place's name + coords into memory so the matcher
    runs at O(N) per query without N DB hits. Call once at the start of an
    ingestion pass."""
    global _NAME_CACHE
    rows = list(
        Place.objects.values_list("id", "name", "lat", "lng")
    )
    _NAME_CACHE = [
        (
            row[0],
            normalize_name(row[1]),
            float(row[2]) if row[2] is not None else None,
            float(row[3]) if row[3] is not None else None,
        )
        for row in rows
    ]


def _invalidate_cache() -> None:
    global _NAME_CACHE
    _NAME_CACHE = None


def _candidate_match(name: str, lat: float | None, lng: float | None,
                     radius_m: float = 150.0) -> int | None:
    """Returns the Place.id of the best match, or None.

    A row matches when the normalized name equals the query AND coords are
    within `radius_m`. If query coords are missing, name-equality alone is
    accepted only for unique names (otherwise refuse to guess).
    """
    if _NAME_CACHE is None:
        prime_cache()
    target = normalize_name(name)
    if not target:
        return None

    by_name = [r for r in _NAME_CACHE if r[1] == target]
    if not by_name:
        return None

    if lat is not None and lng is not None:
        # Filter to those within the radius; pick the closest.
        candidates = []
        for pid, _, plat, plng in by_name:
            if plat is None or plng is None:
                continue
            d = _haversine_m(lat, lng, plat, plng)
            if d <= radius_m:
                candidates.append((d, pid))
        if not candidates:
            return None
        candidates.sort()
        return candidates[0][1]

    # No query coords — only safe to match if there's exactly one same-name row.
    if len(by_name) == 1:
        return by_name[0][0]
    return None


def find_or_create_place(*, name: str, lat: float | None, lng: float | None,
                         area: str = "", category: str = Category.RESTAURANT,
                         defaults: dict | None = None) -> tuple[Place, bool]:
    """Returns (place, created). Search order:

    1. Exact slug lookup (where slug = slugify(name) — cheap repeat-run hit)
    2. Normalized-name + coords (within 150m) cache lookup
    3. Create new Place

    `defaults` is a dict of optional fields to set on creation OR fill in on
    an existing row where the column is currently empty (never overwrites
    non-empty curator-set values). Common keys: address, phone, website,
    description.
    """
    defaults = defaults or {}
    base_slug = slugify(name)[:200] or "place"

    # Step 1: exact slug
    place = Place.objects.filter(slug=base_slug).first()
    if place is None:
        # Or a slug suffix collision (slugify("Karma") matched some other Karma)
        # — only if we have coords to verify it's the same place.
        for candidate in Place.objects.filter(slug__startswith=base_slug + "-"):
            if (lat is not None and lng is not None
                    and candidate.lat is not None and candidate.lng is not None):
                d = _haversine_m(lat, lng,
                                 float(candidate.lat), float(candidate.lng))
                if d <= 150.0:
                    place = candidate
                    break

    # Step 2: normalized name + coords
    if place is None:
        match_id = _candidate_match(name, lat, lng)
        if match_id is not None:
            place = Place.objects.get(pk=match_id)

    if place is not None:
        # Backfill empty fields, never overwrite non-empty ones.
        changed = False
        if place.lat is None and lat is not None:
            place.lat = Decimal(str(lat))
            changed = True
        if place.lng is None and lng is not None:
            place.lng = Decimal(str(lng))
            changed = True
        for k, v in defaults.items():
            if v and not getattr(place, k, None):
                setattr(place, k, v)
                changed = True
        if changed:
            place.save()
            _invalidate_cache()
        return place, False

    # Step 3: create
    place = Place(
        name=name,
        category=category,
        area=area or "",
        lat=Decimal(str(lat)) if lat is not None else None,
        lng=Decimal(str(lng)) if lng is not None else None,
    )
    for k, v in defaults.items():
        if v:
            setattr(place, k, v)
    place.save()
    _invalidate_cache()
    return place, True
