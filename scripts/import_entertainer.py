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
URLS_PATH = TMP / "ent-dubai-onesper.txt"
TITLES_PATH = TMP / "ent-titles.tsv"
OUT_PATH = TMP / "ent-parsed.json"

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
          f"skipped no-title: {skipped_no_title} | dup: {skipped_dup}")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
