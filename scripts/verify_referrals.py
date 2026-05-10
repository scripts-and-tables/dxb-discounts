"""Verify each entry in data/referral_seed.json by fetching its referral_url.

For every brand we GET the referral page, capture HTTP status + a short text
snippet from the response body, and flag entries that look broken
(non-2xx, empty body, or seed-description keywords missing from the page).

Output: data/referrals_enriched.json — same shape as the seed plus
{fetch_status, fetch_error, page_text_snippet, needs_review}.

Idempotent: re-runs overwrite the enriched file. The seed is the source of
truth and is not modified.
"""
import argparse
import concurrent.futures as cf
import gzip
import json
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "referral_seed.json"
DEST = ROOT / "data" / "referrals_enriched.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AE,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip",
}

SNIPPET_LEN = 400
MIN_BODY_CHARS = 200


class _TextExtractor(HTMLParser):
    """Strip HTML and collapse whitespace. Skips <script>/<style> bodies."""

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript") and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self._chunks.append(text)

    @property
    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self._chunks)).strip()


def extract_text(html: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass
    return parser.text


def fetch(url: str, timeout: int = 20) -> tuple[int | None, str, str | None]:
    """Return (status_code_or_None, body_text, error_or_None)."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = resp.status
            if resp.getheader("Content-Encoding") == "gzip":
                try:
                    raw = gzip.decompress(raw)
                except OSError:
                    pass
        try:
            html = raw.decode("utf-8", errors="replace")
        except Exception:
            html = raw.decode("latin-1", errors="replace")
        return status, extract_text(html), None
    except urllib.error.HTTPError as e:
        return e.code, "", f"HTTPError: {e.code} {e.reason}"
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        return None, "", f"{type(e).__name__}: {e}"
    except Exception as e:
        return None, "", f"{type(e).__name__}: {e}"


def description_keywords(description: str) -> list[str]:
    """Pull short tokens from the seed description that should appear on the page.

    Targets currency markers and numbers ("AED 20", "30%", "credit") — these
    are the parts most likely to be repeated verbatim on the brand's page.
    Generic words like "refer", "friend", "earn" are too common to be useful
    as drift signals."""
    tokens = re.findall(r"AED\s*\d+|\d+%|\d+\s*(?:rides|orders|months)|credit|cashback", description, flags=re.IGNORECASE)
    return [t.strip().lower() for t in tokens if t.strip()]


def needs_review(status: int | None, body: str, description: str) -> tuple[bool, str]:
    if status is None:
        return True, "fetch failed"
    if not (200 <= status < 300):
        return True, f"http {status}"
    if len(body) < MIN_BODY_CHARS:
        return True, f"body too short ({len(body)} chars)"
    keywords = description_keywords(description)
    if keywords:
        body_lower = body.lower()
        missing = [k for k in keywords if k not in body_lower]
        if missing:
            return True, f"seed keywords missing: {missing}"
    return False, "ok"


def verify_one(entry: dict) -> dict:
    status, body, err = fetch(entry["referral_url"])
    snippet = body[:SNIPPET_LEN]
    review, reason = needs_review(status, body, entry.get("description", ""))
    return {
        **entry,
        "fetch_status": status,
        "fetch_error": err,
        "page_text_snippet": snippet,
        "needs_review": review,
        "review_reason": reason,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=8, help="Concurrent fetchers.")
    ap.add_argument("--limit", type=int, default=0, help="Verify only the first N entries (smoke test).")
    args = ap.parse_args()

    # Windows console defaults to cp1252; force UTF-8 so em-dashes etc. don't crash prints.
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if not SRC.exists():
        print(f"missing {SRC} — create the seed file first", file=sys.stderr)
        return 1

    seed = json.loads(SRC.read_text(encoding="utf-8"))
    if args.limit:
        seed = seed[: args.limit]

    print(f"verifying {len(seed)} entries against live referral pages...")
    enriched: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, result in enumerate(pool.map(verify_one, seed), start=1):
            enriched.append(result)
            tag = "REVIEW" if result["needs_review"] else "ok"
            print(f"  [{i:>3}/{len(seed)}] {tag:>6} {result['slug']:<32} status={result['fetch_status']} {result['review_reason']}")

    DEST.write_text(json.dumps(enriched, indent=2, ensure_ascii=False), encoding="utf-8")

    review_count = sum(1 for e in enriched if e["needs_review"])
    print()
    print(f"wrote {DEST}")
    print(f"  total: {len(enriched)}")
    print(f"  needs_review: {review_count}")
    by_cat: dict[str, int] = {}
    for e in enriched:
        by_cat[e.get("category", "?")] = by_cat.get(e.get("category", "?"), 0) + 1
    print(f"  by category: {by_cat}")
    if review_count:
        print()
        print("flagged for review:")
        for e in enriched:
            if e["needs_review"]:
                snippet = e["page_text_snippet"][:120].replace("\n", " ")
                print(f"  {e['slug']:<32} ({e['review_reason']}) — {snippet!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
