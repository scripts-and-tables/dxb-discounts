"""Enrich each Dubai Entertainer outlet with its actual offer list.

For every (merchant_id, outlet_id) in entertainer_outlets_dubai.json, fetch
the per-outlet detail JSON and attach the parsed offer list to the outlet
record. The URL slug in /outlets/<slug>/detail is ignored by the server —
only the m and o query params matter — so we can use a placeholder slug.

Output: data/entertainer_outlets_enriched.json — the Dubai outlet list with
an added `offers: [...]` field per outlet (and `offers_fetch_error` on
failures so they're auditable rather than silent).

Pass --limit N to enrich only the first N outlets (handy for smoke tests).
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
SRC = ROOT / "data" / "entertainer_outlets_dubai.json"
DEST = ROOT / "data" / "entertainer_outlets_enriched.json"

DETAIL_URL = "https://www.theentertainerme.com/outlets/x/detail"  # slug "x" is a placeholder; ignored
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.theentertainerme.com/search/outlets",
}

# Fields we keep from each offer — the upstream object has 70+ keys but most
# are UI/analytics noise. Adjust here when the schema changes.
OFFER_FIELDS = (
    "offer_id", "name", "category", "sub_category",
    "voucher_type", "details", "offer_detail", "conditions",
    "savings_estimate_aed", "savings_estimate", "savings_estimate_local_currency",
    "validity_date", "valid_from_date", "static_start_date", "static_end_date",
    "is_alcohol_offer", "is_family_offer", "is_birthday_offer",
    "is_pingable", "is_percentage_offer", "is_freemium_offer", "is_prio_offer",
    "is_check_in_offer", "is_pre_booking",
    "terms_and_conditions", "rules_of_use", "restriction_message",
)


def fetch_offers(merchant_id: int, outlet_id: int, retries: int = 1) -> tuple[list[dict], list[dict], str | None]:
    """Return (otheroffers, hotelpackages, error_message)."""
    url = f"{DETAIL_URL}?m={merchant_id}&o={outlet_id}&type=ajax"
    last_err: str | None = None
    for _ in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                if resp.getheader("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
            data = json.loads(raw)
            if not data.get("success"):
                last_err = f"success=false: {data.get('message')!r}"
                continue
            return data.get("otheroffers", []) or [], data.get("hotelpackages", []) or [], None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(0.5)
    return [], [], last_err


def slim_offer(offer: dict) -> dict:
    return {k: offer.get(k) for k in OFFER_FIELDS if k in offer}


def slim_section(section: dict) -> dict:
    return {
        "section_name": section.get("section_name"),
        "is_delivery_section": section.get("is_delivery_section"),
        "is_monthly_section": section.get("is_monthly_section"),
        "offers": [slim_offer(o) for o in section.get("offers_to_display", [])],
    }


def enrich_one(outlet: dict) -> dict:
    other, hotels, err = fetch_offers(outlet["merchant_id"], outlet["outlet_id"])
    enriched = dict(outlet)
    enriched["offer_sections"] = [slim_section(s) for s in other]
    enriched["hotel_packages"] = [slim_offer(o) for o in hotels]  # same field set works
    enriched["offers_fetch_error"] = err
    return enriched


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, default=None, help="enrich only the first N outlets")
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()

    outlets = json.loads(SRC.read_text(encoding="utf-8"))
    if args.limit:
        outlets = outlets[: args.limit]
    print(f"enriching {len(outlets)} outlets with {args.workers} workers...")

    enriched: list[dict] = []
    failures = 0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, row in enumerate(pool.map(enrich_one, outlets), start=1):
            enriched.append(row)
            if row.get("offers_fetch_error"):
                failures += 1
            if i % 100 == 0 or i == len(outlets):
                print(f"  {i}/{len(outlets)}  failures={failures}", file=sys.stderr)

    DEST.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    total_offers = sum(len(s["offers"]) for o in enriched for s in o.get("offer_sections", []))
    total_hotel = sum(len(o.get("hotel_packages", [])) for o in enriched)
    with_offers = sum(1 for o in enriched if any(s["offers"] for s in o.get("offer_sections", [])))
    print(
        f"\nwrote {DEST}\n"
        f"  outlets enriched: {len(enriched)}\n"
        f"  outlets with at least one offer: {with_offers}\n"
        f"  total offers across all outlets: {total_offers}\n"
        f"  total hotel packages: {total_hotel}\n"
        f"  fetch failures: {failures}"
    )


if __name__ == "__main__":
    main()
