"""Import Elite Club Dubai partner venues from their public UAE brochure
PDF (https://store.eliteclub.global/wp-content/uploads/2024/10/EC-UAE-
BROCHURE-16-October-2024-b-1.pdf, ~30 MB, 89 pages).

The brochure is organised by emirate. Pages 3..45 are Dubai venues
(one venue per page). Each page contains the venue name plus benefit
percentages (room / food / spa / etc.).

Strategy: find the "DUBAI" section header, then for each subsequent
page until the next emirate header, parse the largest non-percentage
text block as the venue name and pull the highest "FOOD BENEFIT"
percentage as the headline (since dining is the most relatable filter
for our catalog). Output a JSON file with Place + Discount specs.
"""
import json
import os
import re
import sys
from pathlib import Path

import pypdf

PDF_PATH = os.environ.get("EC_PDF", r"C:\Users\tverd\AppData\Local\Temp\ec-uae-brochure.pdf")
TMP = Path(os.environ.get("TEMP", "/tmp"))
OUT = TMP / "ec-parsed.json"

EMIRATE_HEADERS = (
    "DUBAI", "ABU DHABI", "SHARJAH", "AJMAN",
    "RAS AL KHAIMAH", "FUJAIRAH", "UMM AL QUWAIN",
)
PCT_RE = re.compile(r"^\s*(?:Up\s*to\s*)?\d+\s*%?\s*$", re.IGNORECASE)
BENEFIT_LINE_RE = re.compile(
    r"(\d+)\s*%[^\n]*\b(ROOM|FOOD|SPA|GYM|BEVERAGE)\s*BENEFIT", re.IGNORECASE,
)


def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:80]


def is_section_header(text: str) -> str | None:
    """Return emirate name if this page is JUST a section header (short text)."""
    stripped = text.strip()
    upper = stripped.upper()
    # Section-header pages are very short — typically 5–60 chars ("DUBAI" alone
    # or "DUBAI\nMORE HOTELS IN"). Venue pages have benefit text and run longer.
    if len(stripped) > 60:
        return None
    first_line = upper.splitlines()[0].strip() if upper else ""
    for s in EMIRATE_HEADERS:
        if first_line == s:
            return s
    return None


# Activity / amenity suffixes that the PDF appends to some venue names —
# strip them so the venue name is clean.
ACTIVITY_SUFFIX_RE = re.compile(
    r"\s*(?:archery|airgun|padel|shooting|club|padel\s*tennis|"
    r"terra\s*cabins|coffee\s*shop|tennis|spa)\b.*$",
    re.IGNORECASE,
)

# pypdf sometimes mangles non-ASCII chars to U+FFFD. Patch known cases.
ENCODING_FIXUPS = [
    ("Swiss�tel", "Swissôtel"),
    ("M�venpick", "Mövenpick"),
    ("Caf�", "Café"),
]

# Known venues whose extracted name needs a manual override because
# the brochure layout confuses pypdf's text extraction.
NAME_OVERRIDES_BY_PAGE = {
    16: "Swissôtel Al Murooj",
    28: "Mövenpick Hotel Jumeirah Village Triangle",
    33: "The Dubai Edition",
    34: "Fairmont Dubai",
    40: "Th8 Palm Dubai",
    44: "TIME Oak Hotel & Suites",
    45: "TIME Grand Plaza Hotel",
}


def clean_name(name: str) -> str:
    for bad, good in ENCODING_FIXUPS:
        name = name.replace(bad, good)
    name = re.sub(r"\s*\(\s*COFFEE\s*SHOP\s*\)\s*", "", name, flags=re.IGNORECASE)
    name = ACTIVITY_SUFFIX_RE.sub("", name).strip()
    return name


def parse_venue_name(text: str) -> str:
    """Return the most likely venue name from a brochure page's text."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # Drop generic/benefit lines
    candidates = []
    for line in lines:
        upper = line.upper()
        if PCT_RE.match(line):
            continue
        if any(k in upper for k in (
            "BENEFIT", "VOUCHER", "DESSERT", "BOTTLE", "GRAPE JUICE",
            "WELCOME DRINK", "POOL ACCESS", "DINING", "F&B",
            "MORE HOTELS", "BEACH ACCESS", "FREE NIGHT", "GYM",
            "SPA", "ROOM ", "FOOD", "BEVERAGE",
        )):
            continue
        # Skip lines that are just "Up to" / "AED 590" / etc
        if re.match(r"^(up\s*to|aed)\b", line, re.I):
            continue
        if line in ("ABRA", "BENEFITS"):
            continue
        # Otherwise this is a content line — venue name fragment.
        candidates.append(line)
    if not candidates:
        return ""
    # Heuristic: combine the first 1-2 short lines. Some brochure pages
    # split the venue name across two lines (e.g. "Movenpick Hotel" on
    # one line, "Apartments Downtown Dubai" on the next).
    name = candidates[0]
    if len(candidates) > 1 and len(candidates[0]) < 30 and len(candidates[1]) < 50:
        # Heuristic: if 2nd line looks like a venue continuation (no all-caps benefit text)
        if not any(k in candidates[1].upper() for k in ("BENEFIT", "VOUCHER")):
            name = f"{candidates[0]} {candidates[1]}"
    return clean_name(name)


def parse_benefits(text: str) -> dict:
    """Extract benefit percentages by category."""
    out = {}
    for m in BENEFIT_LINE_RE.finditer(text):
        pct = int(m.group(1))
        cat = m.group(2).upper()
        out[cat] = max(out.get(cat, 0), pct)
    # The PDF often interleaves "30%\nROOM BENEFIT" on separate lines —
    # do a simpler line-pair scan as a fallback.
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for i in range(len(lines) - 1):
        m1 = re.match(r"^\s*(?:Up\s*to\s*)?(\d+)\s*%?\s*$", lines[i])
        m2 = re.match(r"^(ROOM|FOOD|SPA|GYM|BEVERAGE)\s*BENEFIT", lines[i + 1].upper())
        if m1 and m2:
            pct = int(m1.group(1))
            cat = m2.group(1).upper()
            out[cat] = max(out.get(cat, 0), pct)
    return out


def main():
    pdf = pypdf.PdfReader(PDF_PATH)
    pages = [(i, page.extract_text() or "") for i, page in enumerate(pdf.pages)]

    # Walk through pages, tracking current emirate.
    current_emirate = None
    venues = []  # list of (page_idx, emirate, name, benefits)
    for i, text in pages:
        section = is_section_header(text)
        if section:
            # Pages that are JUST a section header. Some have additional content,
            # but if the page has < 60 chars it's probably just the header.
            if len(text.strip()) < 80 or text.strip().upper().splitlines()[-1] in ("MORE HOTELS IN", section):
                current_emirate = section
                continue
        if current_emirate is None:
            continue  # cover / membership info pages
        name = NAME_OVERRIDES_BY_PAGE.get(i) or parse_venue_name(text)
        benefits = parse_benefits(text)
        if not name or len(name) < 3:
            continue
        venues.append((i, current_emirate, name, benefits))

    print(f"All venues: {len(venues)}")
    by_emirate = {}
    for _, e, _, _ in venues:
        by_emirate[e] = by_emirate.get(e, 0) + 1
    print("By emirate:", by_emirate)
    print()

    # Filter to Dubai
    dubai_venues = [v for v in venues if v[1] == "DUBAI"]
    print(f"Dubai venues: {len(dubai_venues)}")
    for i, e, name, benefits in dubai_venues:
        print(f"  page {i:3d}: {name} | {benefits}")

    # Build Place + Discount specs.
    place_specs = []
    discount_specs = []
    seen_slugs = set()
    for i, _, name, benefits in dubai_venues:
        slug = slugify(name)
        if not slug or slug in seen_slugs:
            slug = slug + "-2"  # cheap dedup
        seen_slugs.add(slug)
        # Headline % = best of food/room/spa/gym/beverage in priority order
        headline = (
            benefits.get("FOOD") or benefits.get("ROOM")
            or benefits.get("SPA") or benefits.get("BEVERAGE")
            or benefits.get("GYM") or 20
        )
        bullet = ", ".join(f"{pct}% {cat.title()}" for cat, pct in benefits.items()) or f"{headline}% off"
        place_specs.append({
            "slug": slug,
            "name": name,
            "area": "Dubai",
            "page": i,
        })
        discount_specs.append({
            "place_slug": slug,
            "discount_slug": ("ec-" + slug)[:200],
            "title": f"Up to {headline}% off via Elite Club",
            "headline_pct": headline,
            "bullet": bullet,
        })

    OUT.write_text(json.dumps({
        "places": place_specs,
        "discounts": discount_specs,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}: {len(place_specs)} places, {len(discount_specs)} discounts")


if __name__ == "__main__":
    main()
