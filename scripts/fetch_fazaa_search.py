"""Pull the full Fazaa offer catalog in one call.

GETs https://newapi.fazaa.ae/api/search with the empty-filter form
(`q=&category=&type=`) and `size=10000`. The server clamps `size` to the
actual total (~7,693), so a single request returns every offer. Pagination
exists (`page` + `size`, Spring-style) but isn't needed at this scale.

Output: data/fazaa_search_raw.json — the `content` array verbatim, every
entry an OFFER row with id/slug/title/subTitle/partnerName/locations.

The Fazaa website (www.fazaa.ae) is gated behind Cloudflare's bot challenge.
The newapi host is NOT — it accepts plain HTTP with no challenge — so this
script is straightforward.
"""
import json
import urllib.request
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "fazaa_search_raw.json"
URL = (
    "https://newapi.fazaa.ae/api/search"
    "?language=en&q=&category=&type=&page=0&size=10000"
)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Encoding": "gzip",
    "Origin": "https://www.fazaa.ae",
    "Referer": "https://www.fazaa.ae/",
}


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
        if resp.getheader("Content-Encoding") == "gzip":
            import gzip
            raw = gzip.decompress(raw)
    data = json.loads(raw)

    total = data.get("total")
    content = data.get("content", [])
    print(f"API total: {total}")
    print(f"got: {len(content)}")
    if total is not None and len(content) != total:
        print(f"WARNING: got {len(content)} but total={total}. Re-run if the diff is large.")

    OUT_PATH.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    slugs = {c.get("slug") for c in content if c.get("slug")}
    print(f"\nwrote {OUT_PATH}")
    print(f"  unique slugs: {len(slugs)}")


if __name__ == "__main__":
    main()
