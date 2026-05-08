"""Pull the full Entertainer outlet catalog for country=AE.

Posts to the public proxy at /search-outlets/merchant-search and paginates
until exhausted. The magic body parameter is `country: "AE"` — without it the
API returns only 8 trending merchants instead of the ~9,600-outlet catalog.

Output: data/entertainer_outlets_raw.json (one big JSON list, every outlet
the API returns for country=AE — includes cross-border outlets that need to
be filtered out in the next step).
"""
import base64
import gzip
import json
import time
import urllib.request
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "entertainer_outlets_raw.json"
PROXY_URL = "https://www.theentertainerme.com/search-outlets/merchant-search"
PAGE_LIMIT = 1000  # Confirmed working; limit=9999 returns 0 bytes.

# These headers matter — without X-Requested-With + Origin/Referer the proxy
# silently returns a 0-byte body. Accept-Encoding: gzip is required because the
# response is always gzipped and we decompress manually below.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip",
    "Origin": "https://www.theentertainerme.com",
    "Referer": "https://www.theentertainerme.com/search/outlets",
    "X-Requested-With": "XMLHttpRequest",
}


def encode_params(payload: dict) -> str:
    """Base64-encode a JSON payload exactly the way the website's JS does it.

    The JS function `jsBase64Encoded` looks complex (it does encodeURIComponent +
    byte fixup) but for ASCII content it's equivalent to plain b64encode of the
    UTF-8 JSON string.
    """
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def fetch_page(offset: int, limit: int) -> dict:
    payload = {
        "country": "AE",
        "location_id": 1,
        "country_id": 1,
        "offset": offset,
        "limit": limit,
        "language": "en",
        "locale": "en",
        "company": "entertainer",
        "platform": "web",
    }
    body = json.dumps({"params": encode_params(payload)}).encode("utf-8")
    req = urllib.request.Request(PROXY_URL, data=body, method="POST", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
        if resp.getheader("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    if not raw:
        raise RuntimeError(f"empty response at offset={offset} (likely missing header or bad payload)")
    return json.loads(raw)


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    all_outlets: list[dict] = []
    offset = 0
    expected_total: int | None = None

    while True:
        resp = fetch_page(offset, PAGE_LIMIT)
        if not resp.get("success"):
            raise RuntimeError(f"API returned success=false: {resp.get('message')!r}")
        data = resp["data"]
        page = data.get("outlets", [])
        if expected_total is None:
            expected_total = data.get("outlets_count")
            print(f"outlets_count from API: {expected_total}")
        all_outlets.extend(page)
        print(f"  offset={offset:5d}  got={len(page):4d}  total_so_far={len(all_outlets):5d}")
        if len(page) < PAGE_LIMIT:
            break
        offset += PAGE_LIMIT
        time.sleep(0.4)

    if expected_total is not None and len(all_outlets) != expected_total:
        print(
            f"WARNING: fetched {len(all_outlets)} but API said {expected_total}. "
            "Pagination may have raced — re-run if the diff is large."
        )

    OUT_PATH.write_text(json.dumps(all_outlets, ensure_ascii=False, indent=2), encoding="utf-8")
    merchants = {o["merchant_id"] for o in all_outlets}
    outlets = {o["outlet_id"] for o in all_outlets}
    print(f"\nwrote {OUT_PATH}")
    print(f"  outlets: {len(all_outlets)} ({len(outlets)} unique outlet_ids)")
    print(f"  merchants: {len(merchants)} unique merchant_ids")


if __name__ == "__main__":
    main()
