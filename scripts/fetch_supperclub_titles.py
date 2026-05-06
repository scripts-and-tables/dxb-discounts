"""Fetch each Dubai Supper Club booking page and extract its og:title via
Python (clean UTF-8) — replaces the earlier curl|grep|sed pipeline that
mangled curly apostrophes."""
import concurrent.futures as cf
import html
import os
import re
import urllib.request
from pathlib import Path

TMP = os.environ.get("TEMP", "/tmp")
URLS = Path(TMP, "sc-dubai.txt").read_text(encoding="utf-8").splitlines()
OUT = Path(TMP, "sc-titles.tsv")

OG_RE = re.compile(rb'<meta property="og:title" content="([^"]+)"', re.IGNORECASE)


def fetch(url: str) -> tuple[str, str]:
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; dxb-discounts/research)"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
        m = OG_RE.search(body)
        if not m:
            return url, ""
        title = m.group(1).decode("utf-8", errors="replace")
        return url, html.unescape(title).strip()
    except Exception as e:
        return url, ""


def main():
    rows: list[tuple[str, str]] = []
    with cf.ThreadPoolExecutor(max_workers=12) as pool:
        for url, title in pool.map(fetch, [u.strip() for u in URLS if u.strip()]):
            rows.append((url, title))

    OUT.write_text("\n".join(f"{u}\t{t}" for u, t in rows), encoding="utf-8")
    empty = sum(1 for _, t in rows if not t)
    print(f"fetched: {len(rows)} | empty: {empty}")
    print(f"written: {OUT}")


if __name__ == "__main__":
    main()
