"""Parse cached Fazaa offer JSONs (data/fazaa_api_raw/*.json) into Place +
Discount specs for the migration. Replaces the title-parsing path —
the API gives us partner.partnerName, locations, exact discount values,
expiry dates, and typed discount values directly.

Output: data/fazaa_api_parsed.json with shape {places: [...], discounts: [...]}.
"""
import html as html_lib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RAW_DIR = ROOT / "data" / "fazaa_api_raw"
DEST = ROOT / "data" / "fazaa_api_parsed.json"

# Fazaa returns category slugs like 'dining', 'beauty-spas', 'fitness',
# 'shopping-retail', 'hotels-resorts', 'entertainment', 'travel',
# 'medical-wellness', 'auto-services', etc. Map to our 4 Place categories.
CATEGORY_MAP = {
    "dining": "restaurant",
    "restaurant": "restaurant",
    "cafe": "restaurant",
    "fast-food": "restaurant",
    "hotels-resorts": "hotel",
    "hotels": "hotel",
    "hotel": "hotel",
    "entertainment": "attraction",
    "attractions": "attraction",
    "travel": "attraction",
    "tourism": "attraction",
    "kids": "attraction",
    "sports": "attraction",
}

# Cities we treat as Dubai (some Fazaa records say "Dubai", some give a
# specific district like "Bur Dubai" or "Jumeirah"). Anything not in this
# allowlist falls back to the city string from the location row.
DUBAI_CITY_HINTS = {
    "dubai", "bur dubai", "jumeirah", "jumeira",
    "downtown", "marina", "deira", "barsha",
}


def strip_html(s: str) -> str:
    """Strip HTML tags from a Fazaa rich-text field. They use Quill, which
    emits <p>, <ol>, <li>, <span>, etc."""
    if not s:
        return ""
    # Convert block tags to newlines
    s = re.sub(r"</(p|li|ol|ul|h[1-6]|div|br)>", "\n", s, flags=re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html_lib.unescape(s)
    s = re.sub(r" ", " ", s)  # nbsp
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def normalize_for_dedup(name: str) -> str:
    n = name.lower()
    n = re.sub(r"\bst\b\.?", "street", n)
    n = re.sub(r"\bave\b\.?", "avenue", n)
    n = re.sub(r"\brd\b\.?", "road", n)
    n = re.sub(r"\b&\b", "and", n)
    n = re.sub(r"[^a-z0-9]+", "", n)
    return n


def slugify(s: str, maxlen: int = 80) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:maxlen] or "place"


def map_category(offer: dict) -> str:
    cats = offer.get("categories") or []
    for c in cats:
        slug = (c.get("categorySlug") if isinstance(c, dict) else None) or ""
        if slug in CATEGORY_MAP:
            return CATEGORY_MAP[slug]
    # Fallback: keyword-based
    name = (offer.get("partner", {}) or {}).get("partnerName", "").lower()
    if any(w in name for w in ("hotel", "resort", "suites")):
        return "hotel"
    if any(w in name for w in ("restaurant", "cafe", "café", "bistro", "grill", "kitchen", "eatery", "diner")):
        return "restaurant"
    if any(w in name for w in ("park", "cinema", "museum", "garden", "ice rink", "entertainment", "adventure", "attraction")):
        return "attraction"
    return "retail"


def map_discount_type(api_type: str | None, value) -> str:
    """Fazaa's discountType seems to be PERCENTAGE / FIXED / BOGO / OTHER."""
    if not api_type:
        return "other"
    t = str(api_type).upper()
    if t == "PERCENTAGE":
        return "percentage"
    if t == "FIXED":
        return "fixed_price"
    if t == "BOGO":
        return "bogo"
    return "other"


def primary_city(offer: dict) -> str:
    locs = offer.get("locations") or []
    cities = [str(l.get("city", "")).strip() for l in locs if l.get("city")]
    if not cities:
        return "UAE"
    # Prefer Dubai if any location is in Dubai
    for c in cities:
        if c.lower() in DUBAI_CITY_HINTS or "dubai" in c.lower():
            return "Dubai"
    return cities[0] or "UAE"


def primary_address(offer: dict) -> str:
    locs = offer.get("locations") or []
    if not locs:
        return ""
    # Pick the first Dubai location, else first overall
    for l in locs:
        if "dubai" in str(l.get("city", "")).lower():
            return l.get("address") or ""
    return locs[0].get("address") or ""


def all_locations_summary(offer: dict, limit: int = 8) -> str:
    """Brief summary of all locations for the description."""
    locs = offer.get("locations") or []
    if not locs:
        return ""
    lines = []
    for l in locs[:limit]:
        nm = l.get("name") or ""
        ct = l.get("city") or ""
        if nm and ct:
            lines.append(f"{nm} ({ct})")
        elif nm:
            lines.append(nm)
        elif ct:
            lines.append(ct)
    if len(locs) > limit:
        lines.append(f"… and {len(locs) - limit} more branches")
    return "\n".join(f"- {ln}" for ln in lines)


def parse_expiry(s: str | None) -> str | None:
    """offerExpiry comes as ISO datetime e.g. '2026-09-30T00:00:00Z'.
    Return YYYY-MM-DD or None."""
    if not s:
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def main():
    files = sorted(RAW_DIR.glob("*.json"))
    print(f"raw files: {len(files)}")

    place_specs: dict[str, dict] = {}  # place_slug → spec
    discount_specs: list[dict] = []
    norm_to_slug: dict[str, str] = {}
    skipped = []

    for f in files:
        offer_slug = f.stem
        try:
            offer = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            skipped.append((offer_slug, f"json:{e}"))
            continue

        partner = offer.get("partner") or {}
        venue = (partner.get("partnerName") or "").strip()
        if not venue:
            # Fall back to localData.en.subTitle (we saw "illy cafe Dubai" there)
            ld = (offer.get("localData") or {}).get("en") or {}
            venue = (ld.get("subTitle") or ld.get("title") or "").strip()
        if not venue or len(venue) < 2 or len(venue) > 180:
            skipped.append((offer_slug, "no-venue"))
            continue

        category = map_category(offer)
        area = primary_city(offer)
        address = primary_address(offer)
        website = (partner.get("partnerLink") or "").strip()
        # Some partner links come without scheme — coerce to https://
        if website and not website.startswith(("http://", "https://")):
            website = f"https://{website}"

        # Localised content
        ld_en = (offer.get("localData") or {}).get("en") or {}
        short_desc = strip_html(ld_en.get("shortDescription") or "")
        full_desc = strip_html(ld_en.get("description") or "")
        loc_summary = all_locations_summary(offer)

        # Build a sensible Place description
        desc_parts = []
        if short_desc:
            desc_parts.append(short_desc)
        if loc_summary:
            desc_parts.append(f"Branches:\n{loc_summary}")
        if not desc_parts:
            desc_parts.append(f"{venue} — UAE venue listed on Fazaa.")
        place_description = "\n\n".join(desc_parts)[:2000]

        # Dedupe Place by normalized venue name
        norm = normalize_for_dedup(venue)
        if norm in norm_to_slug:
            place_slug = norm_to_slug[norm]
        else:
            place_slug = slugify(venue)
            base = place_slug
            i = 2
            while place_slug in place_specs:
                place_slug = f"{base}-{i}"[:80]
                i += 1
            norm_to_slug[norm] = place_slug
            place_specs[place_slug] = {
                "slug": place_slug,
                "name": venue,
                "category": category,
                "area": area,
                "address": address[:1000] if address else "",
                "website": website[:200] if website else "",
                "description": place_description,
            }

        # Build Discount
        discount_value = offer.get("discount")
        try:
            discount_value = int(discount_value) if discount_value is not None else None
        except (TypeError, ValueError):
            discount_value = None
        discount_type = map_discount_type(offer.get("discountType"), discount_value)
        # PERCENTAGE with bogus values (0, >99) → demote to other
        if discount_type == "percentage" and (discount_value is None or not (1 <= discount_value <= 99)):
            discount_type = "other"
            discount_value = None

        if discount_type == "percentage":
            offer_title = f"{venue} — {discount_value}% off with Fazaa"
        elif discount_type == "fixed_price":
            offer_title = f"{venue} — Fixed-price Fazaa offer"
        elif discount_type == "bogo":
            offer_title = f"{venue} — 2-for-1 with Fazaa"
        else:
            offer_title = f"{venue} — Fazaa offer"

        # Discount description = the short pitch + branch list (cap)
        d_desc_parts = []
        if short_desc:
            d_desc_parts.append(short_desc)
        elif ld_en.get("title"):
            d_desc_parts.append(ld_en["title"])
        if loc_summary:
            d_desc_parts.append(f"Branches:\n{loc_summary}")
        d_desc = "\n\n".join(d_desc_parts)[:2000] or f"{venue} — Fazaa offer."

        discount_specs.append({
            "place_slug": place_slug,
            "discount_slug": ("fazaa-" + place_slug)[:200],
            "title": offer_title[:200],
            "discount_type": discount_type,
            "percentage": discount_value if discount_type == "percentage" else None,
            "description": d_desc,
            "terms": (full_desc or "Present a valid Fazaa card.")[:2500],
            "external_url": f"https://www.fazaa.ae/offers/view/{offer_slug}",
            "valid_until": parse_expiry(offer.get("offerExpiry")),
            "is_featured": bool(offer.get("offerFeatured")),
        })

    DEST.write_text(
        json.dumps({"places": list(place_specs.values()), "discounts": discount_specs, "skipped": skipped},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"places: {len(place_specs)}  discounts: {len(discount_specs)}  skipped: {len(skipped)}")
    if skipped:
        print(f"skipped sample: {skipped[:5]}")
    print(f"written: {DEST}")


if __name__ == "__main__":
    main()
