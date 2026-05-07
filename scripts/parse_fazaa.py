"""Parse data/fazaa_titles.tsv (slug<tab>raw_title<tab>bucket) into structured
Place + Discount specs for the Fazaa data migration. Writes
data/fazaa_parsed.json.

Title formats seen:
- "Asha's Restaurant - Discount 35%"
- "GAZEBO Restaurant - 10% Discount"
- "Up to 75% Discount at Pure Gold Jewellers"
- "Falla restaurant - Up to 15% Discount"
- "Discount up to 25% on the bill"
- "Enjoy 30% discount on the best available rate"
- "FRIENDS AVENUE - 20% Discount"
- "Footlocker - 15% Discount"
- "Air Arabia - Enjoy 10% discount on Extra Bundle Bookings"
- "Sheraton Mall of the Emirates Hotel Dubai" (no %)
- "The Retreat Palm Dubai MGallery By Sofitel" (no %)

Strategy: extract the leading venue name (the part before " - " typically),
then independently scan the whole title for a percentage. Anything left
without a parseable % goes through as discount_type=other.
"""
import json
import re
import urllib.parse
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "data" / "fazaa_titles.tsv"
DEST = ROOT / "data" / "fazaa_parsed.json"


PCT_PATTERNS = [
    re.compile(r"\bUp\s+to\s+(\d{1,2})\s*%", re.IGNORECASE),
    re.compile(r"\bDiscount\s+up\s+to\s+(\d{1,2})\s*%", re.IGNORECASE),
    re.compile(r"\bEnjoy\s+(?:a\s+)?(?:Up\s+(?:to\s+)?)?(\d{1,2})\s*%", re.IGNORECASE),
    re.compile(r"\bDiscount\s+(\d{1,2})\s*%", re.IGNORECASE),
    re.compile(r"\b(\d{1,2})\s*%\s*Discount", re.IGNORECASE),
    re.compile(r"\b(\d{1,2})\s*%\s*off\b", re.IGNORECASE),
    re.compile(r"\b(\d{1,2})\s*%", re.IGNORECASE),
]


def extract_pct(title: str) -> int | None:
    for pat in PCT_PATTERNS:
        m = pat.search(title)
        if m:
            try:
                v = int(m.group(1))
                if 1 <= v <= 99:
                    return v
            except ValueError:
                continue
    return None


def extract_venue(title: str) -> str:
    """The venue name is what's left after stripping the offer phrase. Try
    several strategies in order:

    1. Strip leading "Fazaa - " prefix
    2. Split on " - " — take the first half (the venue side)
    3. If the title starts with a discount phrase ("Up to 75% Discount at X"),
       split on " at " and take the right side
    4. Strip trailing parentheticals and dashes
    """
    t = title.strip()

    # Drop leading "Fazaa - " or "Fazaa "
    t = re.sub(r"^Fazaa\s*[-–—]\s*", "", t, flags=re.IGNORECASE)

    # Pattern: "Up to N% Discount at <Venue>" → take the right side
    m = re.match(r"^(?:Up\s+to\s+)?\d{1,2}\s*%\s*[Dd]iscount\s+at\s+(.+)$", t, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Pattern: "Enjoy N% discount on ... at <Venue>" → take after last " at "
    if re.match(r"^(?:Enjoy|Special|Exclusive)\s+", t, re.IGNORECASE) and re.search(r"\s+at\s+", t, re.IGNORECASE):
        parts = re.split(r"\s+at\s+", t, flags=re.IGNORECASE)
        if len(parts) >= 2:
            return parts[-1].strip()

    # Default: split on " - " (or " — " or " – ") — venue is the first chunk
    parts = re.split(r"\s+[-–—]\s+", t, maxsplit=1)
    venue = parts[0].strip()

    # Strip trailing parentheticals, trailing periods/commas
    venue = re.sub(r"\s*\([^)]*\)\s*$", "", venue).strip()
    venue = venue.rstrip(",.;:")

    # Title-case if it's all-caps and longer than ~3 chars
    if venue.isupper() and len(venue) > 3:
        venue = venue.title()
        # Common exceptions
        venue = re.sub(r"\bAnd\b", "and", venue)

    # Tidy spaces
    venue = re.sub(r"\s+", " ", venue).strip()
    return venue


# Areas seen in slugs / titles that indicate a Dubai venue
DUBAI_CUE_RE = re.compile(
    r"\b(dubai|jumeirah|jumeira|jbr|jlt|jvc|difc|downtown|marina|palm|"
    r"business[\s-]*bay|burj|barsha|quoz|sufouh|deira|mirdif|festival[\s-]*city|"
    r"silicon[\s-]*oasis|sheikh[\s-]*zayed|szr|bluewaters|la[\s-]*mer|"
    r"city[\s-]*walk|hatta|al[\s-]*mina|al[\s-]*furjan|dubai[\s-]*hills|"
    r"creek|jaddaf|jebel[\s-]*ali|al[\s-]*wasl|oud[\s-]*metha|al[\s-]*karama|"
    r"al[\s-]*garhoud|umm[\s-]*suqeim|tecom|emirates[\s-]*hills|motor[\s-]*city|"
    r"studio[\s-]*city|al[\s-]*safa|al[\s-]*manara|sustainable[\s-]*city|"
    r"meydan|bur[\s-]*dubai|the[\s-]*greens|the[\s-]*lakes|town[\s-]*square|"
    r"emaar|nakheel|discovery[\s-]*gardens|ibn[\s-]*battuta|al[\s-]*khail|"
    r"miracle[\s-]*garden|ski[\s-]*dubai|dubai[\s-]*mall|mall[\s-]*of[\s-]*emirates|"
    r"safa[\s-]*park|outlet[\s-]*mall|expo|knowledge[\s-]*village|media[\s-]*city)",
    re.IGNORECASE,
)

# Cues that indicate non-Dubai (skip)
NON_DUBAI_CUE_RE = re.compile(
    r"\b(abu[\s-]*dhabi|sharjah|ras[\s-]*al[\s-]*khaimah|fujairah|ajman|"
    r"al[\s-]*ain(?![\s-]*pharmacy)|umm[\s-]*al[\s-]*quwain|yas[\s-]*island)",
    re.IGNORECASE,
)


def is_dubai_or_uae_wide(slug: str, title: str, venue: str) -> tuple[bool, bool]:
    """Returns (keep, dubai_specific).

    - keep=False if the offer is clearly tied to another emirate only.
    - dubai_specific=True if there's a positive Dubai signal we can use as area.
    - For UAE-wide chains (no city signal at all) we keep them with area="UAE".
    """
    haystack = f"{slug} {title} {venue}"
    has_non = bool(NON_DUBAI_CUE_RE.search(haystack))
    has_dubai = bool(DUBAI_CUE_RE.search(haystack))
    if has_non and not has_dubai:
        return False, False
    return True, has_dubai


# Bucket → category mapping
BUCKET_CAT = {
    "restaurant": "restaurant",
    "cafe": "restaurant",
    "hotel": "hotel",
    "spa": "retail",
    "salon": "retail",
    "clinic": "retail",
    "medical": "retail",
    "fitness": "retail",
    "pharmacy": "retail",
    "fashion": "retail",
    "retail": "retail",
    "beauty": "retail",
    "electronics": "retail",
    "education": "retail",
    "auto": "retail",
    "laundry": "retail",
    "travel": "attraction",
    "attraction": "attraction",
}


def guess_category(bucket: str, venue: str, slug: str) -> str:
    haystack = f"{venue} {slug}".lower()
    if bucket in BUCKET_CAT:
        cat = BUCKET_CAT[bucket]
        # Override: a hotel-bucket entry that's clearly a restaurant inside a
        # hotel (e.g. "Verso Italian Restaurant @Grand Hyatt") stays restaurant
        if cat == "hotel" and re.search(r"\brestaurant\b|\bcafe\b|\bcafé\b", haystack):
            return "restaurant"
        return cat
    return "retail"


def normalize_for_dedup(name: str) -> str:
    n = name.lower()
    n = re.sub(r"\bst\b\.?", "street", n)
    n = re.sub(r"\bave\b\.?", "avenue", n)
    n = re.sub(r"\brd\b\.?", "road", n)
    n = re.sub(r"\b&\b", "and", n)
    n = re.sub(r"[^a-z0-9]+", "", n)
    return n


def clean_slug(raw_slug: str) -> str:
    """URL-decode and lowercase a slug from the TSV. Some slugs in the wild
    contain spaces, ampersands, or trailing dashes — keep them as-is so the
    external_url still works, but lowercase for filesystem/db consistency."""
    return urllib.parse.unquote(raw_slug).strip().lower()


def main():
    rows = SRC.read_text(encoding="utf-8").splitlines()
    if rows and rows[0].startswith("slug\t"):
        rows = rows[1:]

    seen_slugs: set[str] = set()
    seen_norm: dict[str, str] = {}  # normalized venue → place_slug
    place_specs: dict[str, dict] = {}
    discount_specs: list[dict] = []
    skipped_non_dubai: list[str] = []

    for line in rows:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        raw_slug, raw_title, bucket = parts[0], parts[1], parts[2]
        slug = clean_slug(raw_slug)
        if not slug or slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        # Strip "Fazaa" suffix titles like the literal title "Fazaa"
        if raw_title.strip().lower() == "fazaa":
            continue

        venue = extract_venue(raw_title)
        if not venue or len(venue) < 2 or len(venue) > 180:
            continue

        keep, dubai_specific = is_dubai_or_uae_wide(slug, raw_title, venue)
        if not keep:
            skipped_non_dubai.append(slug)
            continue

        pct = extract_pct(raw_title)
        category = guess_category(bucket, venue, slug)
        area = "Dubai" if dubai_specific else "UAE"

        # Place: dedupe by normalized venue name
        norm = normalize_for_dedup(venue)
        if norm in seen_norm:
            place_slug = seen_norm[norm]
        else:
            # Make a clean place slug from the venue name (not the URL slug,
            # since URL slugs can be offer-specific like "...-summer-offer")
            place_slug = re.sub(r"[^a-z0-9]+", "-", venue.lower()).strip("-")[:80] or slug[:80]
            i = 2
            base = place_slug
            while place_slug in place_specs:
                place_slug = f"{base}-{i}"[:80]
                i += 1
            seen_norm[norm] = place_slug
            place_specs[place_slug] = {
                "slug": place_slug,
                "name": venue,
                "category": category,
                "area": area,
                "description": f"{venue} — UAE venue listed on Fazaa. Discount details and full terms via fazaa.ae.",
            }

        external_url = f"https://www.fazaa.ae/offers/view/{urllib.parse.quote(slug, safe='-_.')}"
        discount_type = "percentage" if pct else "other"
        if pct:
            offer_title = f"{venue} — {pct}% off with Fazaa"
        else:
            offer_title = f"{venue} — Fazaa offer"

        discount_specs.append({
            "place_slug": place_slug,
            "discount_slug": ("fazaa-" + place_slug)[:200],
            "title": offer_title[:200],
            "discount_type": discount_type,
            "percentage": pct,
            "description": raw_title,
            "external_url": external_url,
            "bucket": bucket,
        })

    DEST.write_text(
        json.dumps(
            {
                "places": list(place_specs.values()),
                "discounts": discount_specs,
                "skipped_non_dubai": skipped_non_dubai,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"places: {len(place_specs)}")
    print(f"discounts: {len(discount_specs)}")
    print(f"skipped (non-Dubai/UAE-irrelevant): {len(skipped_non_dubai)}")
    print(f"written: {DEST}")


if __name__ == "__main__":
    main()
