"""Enrich each Dubai-filtered Fazaa offer with its full detail JSON.

For every slug in fazaa_search_dubai.json, GET /api/offers/slug/<slug> and
attach the response under a `detail` field. Detail carries the real
discount/discountType (search title is marketing fluff), full addresses,
categories, tiers, and localized copy.

Output: data/fazaa_search_enriched.json — the Dubai offer list with a
`detail` dict per row, and `detail_fetch_error` populated on failures so
they're auditable.

Pass --limit N to enrich only the first N offers (handy for smoke tests).
"""
import argparse
import concurrent.futures as cf
import gzip
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "fazaa_search_dubai.json"
DEST = ROOT / "data" / "fazaa_search_enriched.json"

DETAIL_BASE = "https://newapi.fazaa.ae/api/offers/slug/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Encoding": "gzip",
    "Origin": "https://www.fazaa.ae",
    "Referer": "https://www.fazaa.ae/",
}

# Detail has ~19 top-level fields; we keep them all because each is small and
# the schema is stable. If this ever bloats unreasonably, slim it down here.


def fetch_detail(slug: str, retries: int = 1) -> tuple[dict | None, str | None]:
    # Some new partner slugs contain spaces / unicode (e.g. "spret retail").
    # Encode the path segment so urllib doesn't reject the URL outright.
    from urllib.parse import quote
    url = DETAIL_BASE + quote(slug, safe="")
    last_err: str | None = None
    for _ in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                if resp.getheader("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
            return json.loads(raw), None
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if e.code == 404:
                return None, last_err  # don't retry 404s
            time.sleep(0.5)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(0.5)
    return None, last_err


def enrich_one(offer: dict) -> dict:
    slug = offer.get("slug")
    if not slug:
        return {**offer, "detail": None, "detail_fetch_error": "missing slug"}
    detail, err = fetch_detail(slug)
    return {**offer, "detail": detail, "detail_fetch_error": err}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, default=None, help="enrich only the first N offers")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    offers = json.loads(SRC.read_text(encoding="utf-8"))
    if args.limit:
        offers = offers[: args.limit]
    print(f"enriching {len(offers)} offers with {args.workers} workers...")

    enriched: list[dict] = []
    failures = 0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, row in enumerate(pool.map(enrich_one, offers), start=1):
            enriched.append(row)
            if row.get("detail_fetch_error"):
                failures += 1
            if i % 100 == 0 or i == len(offers):
                print(f"  {i}/{len(offers)}  failures={failures}", file=sys.stderr)

    DEST.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")

    # Summary
    with_detail = sum(1 for o in enriched if o.get("detail"))
    discount_types = {}
    for o in enriched:
        if d := o.get("detail"):
            t = d.get("discountType")
            discount_types[t] = discount_types.get(t, 0) + 1
    print(
        f"\nwrote {DEST}\n"
        f"  offers enriched: {len(enriched)}\n"
        f"  offers with detail: {with_detail}\n"
        f"  fetch failures: {failures}\n"
        f"  discount types: {discount_types}"
    )


if __name__ == "__main__":
    main()
