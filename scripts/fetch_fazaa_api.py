"""Pull full offer JSON from Fazaa's public API for every slug we know about.

Slug sources (deduped):
1. Existing Google harvest: data/fazaa_titles.tsv
2. The 25 offers returned by GET /api/offers
3. The ~20 offers in GET /api/home (under home.offers + home.dynamicOffers)

For each slug, fetch GET /api/offers/slug/{slug} and cache the JSON to
data/fazaa_api_raw/{slug}.json. Skips slugs already cached so re-runs are
cheap. Logs any 404s to data/fazaa_api_failed.txt.

This populates a much richer dataset than parsing Google search titles.
Each cached JSON contains: partner.partnerName, partner.partnerLink,
locations[] (name + address + lat/lng), discount, discountType,
offerExpiry, localData.en.{title, shortDescription, description},
categories[], and tiers[].
"""
import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TSV = ROOT / "data" / "fazaa_titles.tsv"
RAW_DIR = ROOT / "data" / "fazaa_api_raw"
FAILED_LOG = ROOT / "data" / "fazaa_api_failed.txt"

API_BASE = "https://newapi.fazaa.ae/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Origin": "https://www.fazaa.ae",
    "Referer": "https://www.fazaa.ae/",
}


def collect_slugs() -> set[str]:
    slugs: set[str] = set()
    # Google harvest
    if TSV.exists():
        for line in TSV.read_text(encoding="utf-8").splitlines()[1:]:
            parts = line.split("\t")
            if parts and parts[0].strip():
                slugs.add(parts[0].strip().lower())
    # /api/offers (25)
    try:
        body = http_get(f"{API_BASE}/offers")
        for o in json.loads(body):
            if o.get("offerSlug"):
                slugs.add(o["offerSlug"].lower())
    except Exception as e:
        print(f"  warn: /api/offers failed: {e}")
    # /api/home (offers + dynamicOffers)
    try:
        body = http_get(f"{API_BASE}/home")
        home = json.loads(body)
        for o in home.get("offers", []):
            if o.get("offerSlug"):
                slugs.add(o["offerSlug"].lower())
        for o in home.get("dynamicOffers", []):
            if o.get("offerSlug"):
                slugs.add(o["offerSlug"].lower())
    except Exception as e:
        print(f"  warn: /api/home failed: {e}")
    return slugs


def http_get(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_one(slug: str) -> tuple[str, str, bytes | None]:
    """Returns (slug, status, body). status is one of 'cached', 'fetched',
    '404', 'err'."""
    cache_path = RAW_DIR / f"{slug}.json"
    if cache_path.exists() and cache_path.stat().st_size > 50:
        return slug, "cached", None
    try:
        body = http_get(f"{API_BASE}/offers/slug/{slug}")
        cache_path.write_bytes(body)
        return slug, "fetched", body
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return slug, "404", None
        return slug, f"http{e.code}", None
    except Exception as e:
        return slug, f"err:{type(e).__name__}", None


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    slugs = sorted(collect_slugs())
    print(f"slugs to process: {len(slugs)}")

    counts = {"cached": 0, "fetched": 0, "404": 0, "err": 0}
    failed: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_one, s): s for s in slugs}
        for i, fut in enumerate(as_completed(futures), 1):
            slug, status, _ = fut.result()
            if status in ("cached", "fetched"):
                counts[status] += 1
            elif status == "404":
                counts["404"] += 1
                failed.append((slug, status))
            else:
                counts["err"] += 1
                failed.append((slug, status))
            if i % 50 == 0:
                print(f"  {i}/{len(slugs)}  cached={counts['cached']} fetched={counts['fetched']} 404={counts['404']} err={counts['err']}")

    print(f"\ndone: cached={counts['cached']} fetched={counts['fetched']} 404={counts['404']} err={counts['err']}")
    if failed:
        FAILED_LOG.write_text(
            "\n".join(f"{s}\t{st}" for s, st in failed),
            encoding="utf-8",
        )
        print(f"failed slugs logged to {FAILED_LOG}")


if __name__ == "__main__":
    main()
