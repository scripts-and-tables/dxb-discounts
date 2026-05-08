"""Pull the full Playbook venue catalog in one call.

POSTs https://app-playbook-prod.azurewebsites.net/api/FetchVenuesWithTrafficData
with TakeCount=10000. The server clamps to the actual total (~1,838 for the
UAE Food & Drink vertical), so a single request returns everything. The
listing rows are place-level metadata only — name, area, lat/lng, images;
the per-venue Highlights (the actual deals) come from enrich_playbook_offers.py.

Output: data/playbook_search_raw.json — the `Venues` array verbatim.

Auth is a single static `ApplicationKey` header lifted from the SPA bundle
(www.my-playbook.com chunk 5210). No tokens, no signing, no captcha — Playbook
just gates the API on this header.

VerticalId mapping (from /GetVersionInfo):
  1 = Sports & Fitness
  2 = Food & Drink
The skill targets VerticalId=2 because that aligns with the dxb-discounts
project's restaurant/cafe focus. To pull sports/fitness instead, override via
--vertical 1.
"""
import argparse
import json
import urllib.request
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "playbook_search_raw.json"
URL = "https://app-playbook-prod.azurewebsites.net/api/FetchVenuesWithTrafficData"
APPLICATION_KEY = "79CC5A25-D046-4B3E-913C-443F8630E952"
HEADERS = {
    "ApplicationKey": APPLICATION_KEY,
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Origin": "https://www.my-playbook.com",
    "Referer": "https://www.my-playbook.com/",
}

# UAE / Dubai centroid — the API uses Lat/Lng for "near me" sort but doesn't
# filter on geography, so anything in the country radius works.
DEFAULT_LAT = 25.20
DEFAULT_LNG = 55.27


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--vertical", type=int, default=2,
                        help="VerticalId — 2=Food&Drink (default), 1=Sports&Fitness")
    parser.add_argument("--country", type=int, default=1, help="CountryId — 1=UAE (default)")
    parser.add_argument("--take", type=int, default=10000, help="TakeCount — server clamps to total")
    args = parser.parse_args()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "CountryId": args.country,
        "Lat": DEFAULT_LAT,
        "Lng": DEFAULT_LNG,
        "VerticalId": args.vertical,
        "OrderBy": 2,
        "OrderByPartnerStatus": True,
        "TakeCount": args.take,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(URL, data=body, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
    data = json.loads(raw)

    venues = data.get("Venues", [])
    busy = data.get("BusyVenues", [])
    print(f"got: {len(venues)} venues  ({len(busy)} BusyVenues)")

    # Sanity: dedupe by Id (the listing should already be unique, but verify).
    ids = [v.get("Id") for v in venues]
    unique = set(ids)
    if len(unique) != len(ids):
        print(f"WARNING: {len(ids) - len(unique)} duplicate Ids in listing.")

    OUT_PATH.write_text(json.dumps(venues, ensure_ascii=False, indent=2), encoding="utf-8")

    states = {}
    for v in venues:
        s = v.get("StateName", "-")
        states[s] = states.get(s, 0) + 1
    print(f"\nwrote {OUT_PATH}")
    print(f"  unique Ids: {len(unique)}")
    print(f"  by state:   {sorted(states.items(), key=lambda x: -x[1])}")


if __name__ == "__main__":
    main()
