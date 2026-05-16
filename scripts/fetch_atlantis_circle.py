"""Fetch Atlantis Circle source pages from atlantis.com.

Pulls the per-venue detail HTML for the 20 Circle-participating restaurants
across Atlantis The Palm + Atlantis The Royal. Each page has clean
schema.org Restaurant JSON-LD with name, address, lat/lng, phone, cuisine,
image, and description — that's what the parser feeds on.

Strategy: try live `www.atlantis.com` first (short timeout — their CDN
appears to geo-block some egress IPs, so don't wait long). If a request
times out / returns non-2xx, fall back to `web.archive.org/web/2026/...`
which mirrors the same HTML reliably. The membership / dining listing
pages are JS-rendered SPAs (the venue list isn't in the HTML), so this
script only fetches the per-venue detail pages — the venue inventory is
hard-coded from migration 0026 in parse_atlantis_circle.py.

Output: `data/_atlantis_probe/{slug}.html` for every venue + a
`fetch_report.json` summarising which source (live vs archive) served each
page and any failures.

Re-running is cheap — pages already on disk are skipped unless `--force`
is passed.
"""
from __future__ import annotations

import argparse
import gzip
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROBE_DIR = ROOT / "data" / "_atlantis_probe"

# (atlantis URL segment, our Place.slug from migration 0026) — must stay in
# sync with apps/discounts/migrations/0026_atlantis_circle_venues.py.
VENUES = [
    # Atlantis The Palm
    ("hakkasan",                          "hakkasan-atlantis-the-palm"),
    ("ossiano",                           "ossiano"),
    ("saffron",                           "saffron-atlantis"),
    ("kaleidoscope",                      "kaleidoscope"),
    ("wavehouse",                         "wavehouse"),
    ("gordon-ramsay-bread-street-kitchen","gordon-ramsay-bread-street-kitchen"),
    ("street-pizza",                      "street-pizza-atlantis"),
    ("ayamna",                            "ayamna"),
    ("seafire-steakhouse",                "seafire-steakhouse"),
    ("en-fuego",                          "en-fuego"),
    # Atlantis The Royal
    ("dinner-by-heston",                  "dinner-by-heston-blumenthal"),
    ("milos",                             "estiatorio-milos"),
    ("cloud22",                           "cloud22"),
    ("the-royal-tearoom",                 "the-royal-tearoom"),
    ("arianas-kitchen",                   "arianas-persian-kitchen"),
    ("jaleo",                             "jaleo-by-jose-andres"),
    ("ling-ling",                         "ling-ling-atlantis"),
    ("nobu-by-the-beach",                 "nobu-by-the-beach"),
    ("gastronomy",                        "gastronomy-atlantis"),
    ("la-mar",                            "la-mar-by-gaston-acurio"),
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
LIVE_BASE = "https://www.atlantis.com/dubai/dining"
ARCHIVE_BASE = "https://web.archive.org/web/2026/https://www.atlantis.com/dubai/dining"
LIVE_TIMEOUT = 8       # seconds — don't wait long for the live host
ARCHIVE_TIMEOUT = 30   # seconds — archive.org redirects then serves; be patient


def _fetch(url: str, timeout: int) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
        return body


def fetch_venue(url_segment: str) -> tuple[bytes, str]:
    """Returns (html_bytes, source) where source ∈ {'live','archive','fail'}.

    Tries live atlantis.com first (short timeout). Falls back to web.archive.org.
    Returns (b'', 'fail') if both attempts fail.
    """
    live_url = f"{LIVE_BASE}/{url_segment}"
    try:
        return _fetch(live_url, LIVE_TIMEOUT), "live"
    except (urllib.error.URLError, TimeoutError, OSError):
        pass
    archive_url = f"{ARCHIVE_BASE}/{url_segment}"
    try:
        return _fetch(archive_url, ARCHIVE_TIMEOUT), "archive"
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"   FAIL {url_segment}: {e}")
        return b"", "fail"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="re-fetch venues even if their HTML is already on disk")
    args = parser.parse_args()

    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    report: dict = {"venues": {}, "fetched_at": int(time.time())}
    counts = {"live": 0, "archive": 0, "fail": 0, "cached": 0}

    for url_segment, place_slug in VENUES:
        out_path = PROBE_DIR / f"{place_slug}.html"
        if out_path.exists() and not args.force:
            print(f"   skip {place_slug:40s} (cached)")
            counts["cached"] += 1
            report["venues"][place_slug] = {"source": "cached", "bytes": out_path.stat().st_size,
                                            "url_segment": url_segment}
            continue
        body, source = fetch_venue(url_segment)
        if source != "fail":
            out_path.write_bytes(body)
            print(f"   {source:>8} {place_slug:40s} {len(body):>7} bytes")
        counts[source] += 1
        report["venues"][place_slug] = {"source": source, "bytes": len(body),
                                        "url_segment": url_segment}

    (PROBE_DIR / "fetch_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(f"\nDone. live={counts['live']} archive={counts['archive']} "
          f"fail={counts['fail']} cached={counts['cached']}")
    print(f"Output: {PROBE_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
