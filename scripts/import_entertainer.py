"""End-to-end importer for The Entertainer's Dubai outlets.

Steps:
1. Read the pre-filtered list of Dubai merchant URLs from
   $TEMP/ent-dubai-onesper.txt (one URL per merchant slug).
2. Fetch og:title for each in parallel.
3. Parse the standard "<Venue>, <Area> - Top Offers" pattern.
4. Emit a JSON blob to $TEMP/ent-parsed.json with Place + Discount specs.

A second script (gen_entertainer_migration.py) reads the JSON and writes
the actual data migration.
"""
import concurrent.futures as cf
import html
import json
import os
import re
import urllib.request
from pathlib import Path

TMP = Path(os.environ.get("TEMP", "/tmp"))
# Optionally override the URL list and the output filename via env vars so the
# same script can fetch the full sitemap or a pre-filtered subset.
URLS_PATH = Path(os.environ.get("ENT_URLS", str(TMP / "ent-all-urls.txt")))
TITLES_PATH = Path(os.environ.get("ENT_TITLES", str(TMP / "ent-titles.tsv")))
OUT_PATH = Path(os.environ.get("ENT_PARSED", str(TMP / "ent-parsed.json")))

# Match an area string against Dubai. The check runs case-insensitively on
# the area portion of the title, so "Downtown Dubai" or "JLT - Jumeirah Lake
# Towers" both match.
DUBAI_AREA_RE = re.compile(
    r"\b(?:dubai|jumeirah|jbr|jlt|jvc|difc|downtown|marina|palm|business\s*bay|"
    r"burj|barsha|quoz|sufouh|deira|mirdif|festival\s*city|silicon\s*oasis|"
    r"sheikh\s*zayed|szr|bluewaters|la\s*mer|city\s*walk|hatta|al\s*mina|"
    r"al\s*furjan|dubai\s*hills|town\s*square|al\s*madinat|emirates\s*hills|"
    r"al\s*qasr|mina\s*a\s*salam|al\s*qudra|festival\s*plaza|the\s*greens|"
    r"the\s*lakes|wafi|dubai\s*creek|creek\s*harbour|ras\s*al\s*khor|"
    r"dubai\s*marina|al\s*mamzar|al\s*warqaa|al\s*mizhar|bur\s*dubai|"
    r"al\s*sufouh|jumeirah\s*lake|jumeirah\s*village|al\s*nahda|"
    r"meydan|nad\s*al\s*sheba|culture\s*village|festival\s*city|"
    r"international\s*city|sports\s*city|knowledge\s*village|media\s*city|"
    r"internet\s*city|healthcare\s*city|production\s*city|"
    r"investment\s*park|outlet\s*village|expo|"
    # Round 2 — areas missed in the first pass
    r"al\s*jaddaf|jebel\s*ali|al\s*wasl|oud\s*metha|al\s*karama|al\s*garhoud|"
    r"umm\s*suqeim|umm\s*hurair|d3|design\s*district|tecom|emirates\s*living|"
    r"motor\s*city|studio\s*city|impz|production\s*city|al\s*sufouh|"
    r"al\s*safa|al\s*manara|al\s*jafiliya|jaddaf|jaffliya|"
    r"emaar|sustainable\s*city|jumeira|nakheel|al\s*meydan|"
    r"discovery\s*gardens|ibn\s*battuta|al\s*khail)\b",
    re.IGNORECASE,
)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

OG_TITLE_RE = re.compile(rb'<meta property="og:title" content="([^"]+)"', re.IGNORECASE)
OG_DESC_RE = re.compile(rb'<meta property="og:description" content="([^"]+)"', re.IGNORECASE)


def url_merchant_slug(url: str) -> str:
    """`/outlets/<slug>/detail?...` → `<slug>`"""
    m = re.search(r"/outlets/([^/]+)/", url)
    return m.group(1) if m else ""


def fetch_one(url: str) -> tuple[str, str, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
        title_m = OG_TITLE_RE.search(body)
        desc_m = OG_DESC_RE.search(body)
        title = html.unescape(title_m.group(1).decode("utf-8", errors="replace")) if title_m else ""
        desc = html.unescape(desc_m.group(1).decode("utf-8", errors="replace")) if desc_m else ""
        return url, title.strip(), desc.strip()
    except Exception:
        return url, "", ""


# Pattern: "Venue Name, Area - Top Offers"
TITLE_RE = re.compile(r"^(.+?)\s*-\s*Top Offers\s*$", re.IGNORECASE)


def parse_title(title: str) -> tuple[str, str] | None:
    """Return (venue, area) or None."""
    if not title:
        return None
    m = TITLE_RE.match(title)
    if not m:
        # Fallback: use whole title as venue, area empty
        body = title
    else:
        body = m.group(1).strip()
    # Split last comma → venue, area
    if "," in body:
        venue, area = body.rsplit(",", 1)
        return venue.strip(), area.strip()
    return body, "Dubai"


def make_slug_from_merchant(merchant_slug: str) -> str:
    """Use the merchant slug from the URL directly; it's already lowercased."""
    return merchant_slug[:80]


def main():
    urls = [u.strip() for u in URLS_PATH.read_text(encoding="utf-8").splitlines() if u.strip()]
    print(f"Fetching {len(urls)} URLs in parallel...")

    rows = []
    with cf.ThreadPoolExecutor(max_workers=14) as pool:
        for i, result in enumerate(pool.map(fetch_one, urls), start=1):
            rows.append(result)
            if i % 25 == 0:
                print(f"  {i}/{len(urls)}")

    # Persist raw titles for debugging
    TITLES_PATH.write_text(
        "\n".join(f"{u}\t{t}\t{d}" for u, t, d in rows),
        encoding="utf-8",
    )
    print(f"Wrote {TITLES_PATH}")

    # Parse into Place + Discount specs.
    place_specs = {}  # slug -> spec
    discount_specs = []
    skipped_no_title = 0
    skipped_dup = 0
    skipped_not_dubai = 0

    for url, title, _desc in rows:
        if not title:
            skipped_no_title += 1
            continue
        merchant = url_merchant_slug(url)
        if not merchant:
            continue
        parsed = parse_title(title)
        if not parsed:
            continue
        venue, area = parsed
        if len(venue) < 2 or len(venue) > 200:
            continue
        # Filter by area: only keep merchants whose area looks like a Dubai location.
        if not DUBAI_AREA_RE.search(area):
            skipped_not_dubai += 1
            continue
        slug = make_slug_from_merchant(merchant)
        if slug in place_specs:
            skipped_dup += 1
            continue
        place_specs[slug] = {
            "slug": slug,
            "name": venue,
            "area": area or "Dubai",
            "url": url.split("?")[0],  # strip ?m=&o= query
        }
        discount_specs.append({
            "place_slug": slug,
            "discount_slug": ("ent-" + slug)[:200],
            "title": f"Buy One Get One Free at {venue} via The Entertainer",
            "external_url": url.split("?")[0],
        })

    OUT_PATH.write_text(json.dumps({
        "places": list(place_specs.values()),
        "discounts": discount_specs,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"places: {len(place_specs)} | discounts: {len(discount_specs)} | "
          f"skipped no-title: {skipped_no_title} | not-dubai: {skipped_not_dubai} | dup: {skipped_dup}")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
