"""Pull the full ADCB TouchPoints partner-offer catalog from offers.adcb.com.

The site is a Vue SPA backed by `offersApi`. Most calls have an OAuth
Bearer interceptor, but the offer-list endpoint accepts anonymous GETs
when called with the right `marketplaceId` + `offerType` query — the
auth interceptor is a no-op when no token is in localStorage.

This script paginates `/offersApi/api/v1/offers/offersList` across the
flat-discount offerType buckets (everything that isn't TouchPoints-
redemption or Bonus-TouchPoints earning). It fetches both English and
Arabic localData in one shot — the API returns both languages per
record.

Output: `data/adcb_offers_raw.json` — flat list of every offer the API
returns for the UAE (~3,100 records). Filtering to Dubai happens in
filter_adcb_dubai.py.

The flat-discount bucket combines five offerType values that the SPA
treats as one segment:
  'Fixed-value', 'Discount', 'Free-format', 'Physical bond', 'Bank Offers'

Re-running is cheap — the API is fast and we always pull fresh.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "adcb_offers_raw.json"

BASE = "https://offers.adcb.com/offersApi/api/v1/offers/offersList"
MARKETPLACE_ID = "785c2068-2afb-4c4e-8393-9d40941d88d1"
PAGE_SIZE = 100
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
# The five offerType values the SPA bundles together for its "discount" view.
# Sent as a single comma-separated literal-quoted string, exactly how the SPA
# does it (see chunk `touchpoints.*.js`). Including the inner quotes matters.
OFFER_TYPE = "'Fixed-value','Discount','Free-format','Physical bond','Bank Offers'"


def _fetch_page(page_index: int) -> dict:
    params = {
        "marketplaceId": MARKETPLACE_ID,
        "pageIndex": page_index,
        "pageSize": PAGE_SIZE,
        "offerType": OFFER_TYPE,
        "sort": "updated",
    }
    url = f"{BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://offers.adcb.com",
        "Referer": "https://offers.adcb.com/offer/websites/personal/touchpoints-offers/",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    all_items: list[dict] = []
    page = 1
    while True:
        payload = _fetch_page(page)
        if not payload.get("success"):
            raise RuntimeError(f"page {page}: API said success=False — {payload.get('message')}")
        data = payload.get("data") or {}
        items = data.get("items") or []
        total_pages = data.get("totalPage") or 1
        total_count = data.get("totalCount") or 0
        print(f"  page {page}/{total_pages}: +{len(items)} items "
              f"({len(all_items) + len(items)}/{total_count})")
        all_items.extend(items)
        if page >= total_pages or not items:
            break
        page += 1
        time.sleep(0.2)  # polite spacing — ADCB has no published rate limit
    OUT_PATH.write_text(json.dumps(all_items, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {len(all_items)} offers -> {OUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
