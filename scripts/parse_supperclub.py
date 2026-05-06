"""One-off helper: parse /tmp/sc-titles.tsv (URL<tab>og:title for Supper Club
Dubai bookings) into structured Place + Discount specs for a Django data
migration. Prints a JSON blob to stdout that the migration imports.
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


import os
TMP = os.environ.get("TEMP", "/tmp")
SRC = Path(TMP) / "sc-titles.tsv"
DEST = Path(TMP) / "sc-parsed.json"


# Venues whose name contains the word "spa", "wellness", "club", "pool",
# "beach" → category guesses below.
def guess_category(venue: str, area: str) -> str:
    haystack = (venue + " " + area).lower()
    if any(w in haystack for w in ("spa", "wellness", "salon")):
        return "retail"
    if any(w in haystack for w in (
        "pool", "beach", "rooftop", "skypool", "daycation",
    )):
        return "hotel"
    # If the venue name itself looks like a hotel brand
    hotel_keywords = ("hotel", "resort", "hilton", "marriott", "hyatt",
                       "rotana", "anantara", "edition", "raffles",
                       "shangri", "conrad", "ritz", "sheraton", "fairmont",
                       "sofitel", "address", "intercontinental", "renaissance",
                       "westin", "movenpick", "doubletree", "voco",
                       "dukes", "five", "atlantis", "kempinski")
    if any(w in haystack for w in hotel_keywords):
        # Likely a restaurant inside a hotel — still call it RESTAURANT
        # unless the venue name itself IS the hotel
        if venue.lower() in haystack or any(venue.lower().startswith(w) for w in hotel_keywords):
            return "hotel"
    return "restaurant"


def url_slug(url: str) -> str:
    p = urlparse(url).path
    return p.rstrip("/").rsplit("/", 1)[-1]


PERCENT_RE = re.compile(r"\b(\d{1,2})\s*%", re.IGNORECASE)
BOGO_RE = re.compile(r"\b(buy\s+1\s+get\s+1|b1g1|2-for-1|two[- ]for[- ]one)\b", re.IGNORECASE)


def parse_offer(title: str) -> tuple[str, int | None, str]:
    """Return (discount_type, percentage_or_none, headline_phrase).
    headline_phrase is the offer text up to and including the first " at ".
    """
    m = PERCENT_RE.search(title)
    if m:
        return "percentage", int(m.group(1)), ""
    if BOGO_RE.search(title):
        return "bogo", None, ""
    return "percentage", 25, ""  # fallback default


def parse_title(title: str) -> dict | None:
    """Parse 'X% Off Y at Venue, Area' → dict with venue/area/percentage/etc."""
    if not title:
        return None
    # Strip site suffix
    title = re.sub(r"\s*\|\s*Supper.*$", "", title, flags=re.IGNORECASE).strip()
    title = re.sub(r"\s+", " ", title)

    discount_type, percentage, _ = parse_offer(title)

    # Find last ' at ' (case-insensitive) — splits offer from venue
    parts = re.split(r"\s+at\s+", title, flags=re.IGNORECASE)
    if len(parts) >= 2:
        venue_and_area = parts[-1].strip()
    else:
        venue_and_area = title.strip()

    # Strip trailing parentheticals like " (25% Off)", " (Limited)", etc.
    venue_and_area = re.sub(r"\s*\([^)]+\)\s*$", "", venue_and_area).strip()
    # Strip trailing dashes/separators
    venue_and_area = re.sub(r"\s*[-–—]\s*$", "", venue_and_area).strip()

    # Split venue from area on the LAST comma
    if "," in venue_and_area:
        venue, area = venue_and_area.rsplit(",", 1)
        venue = venue.strip()
        area = area.strip()
    else:
        venue = venue_and_area.strip()
        area = "Dubai"

    # Strip parentheticals from venue too
    venue = re.sub(r"\s*\([^)]+\)\s*$", "", venue).strip()
    # Some areas are like "Dubai" or "Palm Jumeirah Dubai" — clean up.
    area = re.sub(r"\bDubai\b\s*$", "", area).strip(", ").strip()
    area = re.sub(r"\s*\([^)]+\)\s*$", "", area).strip()
    if not area:
        area = "Dubai"

    return {
        "venue": venue,
        "area": area,
        "discount_type": discount_type,
        "percentage": percentage,
        "title": title,
    }


def normalize_for_dedup(name: str) -> str:
    """Normalize a venue name for fuzzy dedup: lowercase, expand common
    abbreviations (St → Street), strip non-alphanumeric."""
    n = name.lower()
    n = re.sub(r"\bst\b\.?", "street", n)
    n = re.sub(r"\bave\b\.?", "avenue", n)
    n = re.sub(r"\brd\b\.?", "road", n)
    n = re.sub(r"\b&\b", "and", n)
    n = re.sub(r"[^a-z0-9]+", "", n)
    return n


def make_place_slug(url_slug_str: str, venue: str) -> str:
    """Use the URL slug truncated, ensuring uniqueness via venue prefix."""
    # url_slug already unique by definition (came from sitemap)
    # but it's offer+venue. We want a place slug that's just the venue.
    # Heuristic: take venue, slugify.
    s = re.sub(r"[^a-z0-9]+", "-", venue.lower()).strip("-")
    return s[:80] or url_slug_str[:80]


def main():
    rows = []
    place_specs = {}  # slug -> spec
    discount_specs = []
    seen_place_slugs: set[str] = set()
    seen_url_slugs: set[str] = set()
    norm_to_slug: dict[str, str] = {}  # normalized name -> place slug, for fuzzy dedup

    for line in SRC.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            url, title = line.split("\t", 1)
        except ValueError:
            continue
        if not title:
            continue
        url_s = url_slug(url)
        if url_s in seen_url_slugs:
            continue
        seen_url_slugs.add(url_s)

        parsed = parse_title(title)
        if not parsed:
            continue
        venue = parsed["venue"]
        area = parsed["area"]
        if len(venue) < 2 or len(venue) > 200:
            continue

        # Fuzzy dedup: if a venue with the same normalized name already
        # exists, reuse its slug.
        norm = normalize_for_dedup(venue)
        if norm in norm_to_slug:
            place_slug = norm_to_slug[norm]
        else:
            place_slug = make_place_slug(url_s, venue)
            original = place_slug
            i = 2
            while place_slug in seen_place_slugs:
                place_slug = f"{original}-{i}"[:80]
                i += 1
            seen_place_slugs.add(place_slug)
            norm_to_slug[norm] = place_slug

        if place_slug not in place_specs:
            place_specs[place_slug] = {
                "slug": place_slug,
                "name": venue,
                "category": guess_category(venue, area),
                "area": area or "Dubai",
                "address": "",
                "phone": "",
                "website": "",
                "description": f"{venue} — Dubai venue listed on Supper Club ME. Booking and offer details available via supperclubme.com.",
            }

        discount_specs.append({
            "place_slug": place_slug,
            "url_slug": url_s,
            "discount_slug": ("supper-" + url_s)[:200],
            "title": parsed["title"],
            "discount_type": parsed["discount_type"],
            "percentage": parsed["percentage"],
            "description": f"{parsed['title']}. Available to Supper Club ME members; book via the Supper Club app for current pricing and availability.",
            "terms": "Valid for Supper Club ME members. Offer details and availability subject to change — confirm via supperclubme.com.",
        })

    DEST.write_text(json.dumps({
        "places": list(place_specs.values()),
        "discounts": discount_specs,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"places: {len(place_specs)}")
    print(f"discounts: {len(discount_specs)}")
    print(f"written: {DEST}")


if __name__ == "__main__":
    main()
