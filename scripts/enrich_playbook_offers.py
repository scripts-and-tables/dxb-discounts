"""Enrich each Dubai-filtered Playbook venue with its full detail JSON.

For every Id in playbook_search_dubai.json, POST /api/FetchVenueDetails with
body `{"Id": <id>}` and attach the response under a `detail` field. Detail
carries the actual deals as a `Highlights` array (each `{Id, Name,
GeneralDescription, DetailedDescription}`), plus `Phone`, `WebsiteUrl`,
`InstagramUrl`, `OpeningHours`, `About`, `ReservationUrl`, etc.

Output: data/playbook_search_enriched.json — the Dubai venue list with a
`detail` dict per row, and `detail_fetch_error` populated on failures.

Pass --limit N to enrich only the first N venues (handy for smoke tests).
"""
import argparse
import concurrent.futures as cf
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "playbook_search_dubai.json"
DEST = ROOT / "data" / "playbook_search_enriched.json"

DETAIL_URL = "https://app-playbook-prod.azurewebsites.net/api/FetchVenueDetails"
APPLICATION_KEY = "79CC5A25-D046-4B3E-913C-443F8630E952"
HEADERS = {
    "ApplicationKey": APPLICATION_KEY,
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Origin": "https://www.my-playbook.com",
    "Referer": "https://www.my-playbook.com/",
}


def fetch_detail(venue_id: int, retries: int = 1) -> tuple[dict | None, str | None]:
    body = json.dumps({"Id": venue_id}).encode("utf-8")
    last_err: str | None = None
    for _ in range(retries + 1):
        try:
            req = urllib.request.Request(DETAIL_URL, data=body, headers=HEADERS, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
            obj = json.loads(raw)
            # Server returns 200 with {StatusCode:404, Message:"NotFound"} for
            # venue IDs it can't resolve — surface that as an error.
            if isinstance(obj, dict) and obj.get("StatusCode") and obj.get("StatusCode") != 200:
                return None, f"app-level {obj.get('StatusCode')}: {obj.get('Message')}"
            return obj, None
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if e.code == 404:
                return None, last_err
            time.sleep(0.5)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(0.5)
    return None, last_err


def enrich_one(venue: dict) -> dict:
    venue_id = venue.get("Id")
    if not venue_id:
        return {**venue, "detail": None, "detail_fetch_error": "missing Id"}
    detail, err = fetch_detail(venue_id)
    return {**venue, "detail": detail, "detail_fetch_error": err}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, default=None, help="enrich only the first N venues")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    venues = json.loads(SRC.read_text(encoding="utf-8"))
    if args.limit:
        venues = venues[: args.limit]
    print(f"enriching {len(venues)} venues with {args.workers} workers...")

    enriched: list[dict] = []
    failures = 0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, row in enumerate(pool.map(enrich_one, venues), start=1):
            enriched.append(row)
            if row.get("detail_fetch_error"):
                failures += 1
            if i % 100 == 0 or i == len(venues):
                print(f"  {i}/{len(venues)}  failures={failures}", file=sys.stderr)

    DEST.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")

    # Summary — count venues with usable Highlights and total deal count.
    with_detail = sum(1 for v in enriched if v.get("detail"))
    with_highlights = sum(1 for v in enriched
                          if v.get("detail") and v["detail"].get("Highlights"))
    total_highlights = sum(len(v["detail"].get("Highlights") or [])
                           for v in enriched if v.get("detail"))
    print(
        f"\nwrote {DEST}\n"
        f"  venues enriched:       {len(enriched)}\n"
        f"  venues with detail:    {with_detail}\n"
        f"  venues with highlights: {with_highlights}\n"
        f"  total highlights (deals): {total_highlights}\n"
        f"  fetch failures:         {failures}"
    )


if __name__ == "__main__":
    main()
