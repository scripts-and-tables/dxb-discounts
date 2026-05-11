"""Resolve a best-candidate logo URL for every Place in the audit JSON.

Cascade per Place (first hit wins):
  1. Entertainer  - data/entertainer_outlets_enriched.json -> `merchant_logo`
                    (direct brand-curated CDN URL). Highest confidence.
  2. Playbook     - data/playbook_search_enriched.json -> `detail.WebsiteUrl`
                    (resolves a clean brand domain we can use). Medium.
  3. Clearbit Autocomplete
                  - https://autocomplete.clearbit.com/v1/companies/suggest
                    Resolves a domain from a free-text brand name. The Logo
                    API itself was retired in 2023, so we keep only the
                    domain hint and pair it with icon.horse for the icon.
  4. HTML parse   - GET the Place's existing website, parse the head for
                    <link rel="apple-touch-icon">, <link rel="icon">, or
                    <meta property="og:image">. Best for places that
                    already have a `website` but lost their Clearbit logo.
  5. icon.horse   - last-resort fallback when a domain is known but no
                    higher-quality logo was found. Always returns *some*
                    PNG, even for nonexistent domains, so confidence=low.

Output: data/place_icons_enriched.json - one row per Place with both
`suggested_website` (downstream can apply to Place.website) AND
`suggested_logo_url` (downstream can apply to Place.logo_url_override).

Pass --limit N to resolve only the first N rows (smoke testing).
Pass --no-clearbit / --no-html to disable specific cascade tiers.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import gzip
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

# Ensure the project root is on sys.path so the lib helper imports cleanly
# regardless of where the script is invoked from.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.lib.name_match import normalize  # noqa: E402

AUDIT = ROOT / "data" / "place_icons_audit.json"
ENTERTAINER = ROOT / "data" / "entertainer_outlets_enriched.json"
FAZAA = ROOT / "data" / "fazaa_search_enriched.json"
PLAYBOOK = ROOT / "data" / "playbook_search_enriched.json"
DEST = ROOT / "data" / "place_icons_enriched.json"

# Fazaa serves partner logos from its API host. The enriched JSON stores
# relative paths like "/upload/partners/celio-...jpeg" — prepend this base.
FAZAA_CDN = "https://api.fazaa.ae"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept": "*/*", "Accept-Encoding": "gzip"}
HEAD_HEADERS = {"User-Agent": UA, "Accept": "image/*,*/*;q=0.8"}


# ---------- helpers ----------

def _extract_domain(url: str) -> str:
    if not url:
        return ""
    try:
        p = urllib.parse.urlparse(url if "://" in url else f"https://{url}")
        host = (p.netloc or p.path or "").strip("/")
        return host.removeprefix("www.")
    except ValueError:
        return ""


def head_image_ok(url: str, timeout: float = 8.0, retries: int = 1) -> bool:
    """Return True if `url` HEADs as a 2xx response with an image content-type.

    icon.horse is treated as always-OK: it guarantees a 200 response for any
    domain (returning a generic favicon when the brand is unknown), so the
    HEAD round-trip would just waste a request and amplify rate-limit risk.
    """
    if not url:
        return False
    if "icon.horse/icon/" in url:
        return True
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEAD_HEADERS, method="HEAD")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if not (200 <= resp.status < 300):
                    return False
                ct = (resp.getheader("Content-Type") or "").lower()
                return ct.startswith("image/")
        except Exception as e:  # noqa: BLE001 - network/URL edge cases vary; any failure -> next tier
            last_err = e
            if attempt < retries:
                import time
                time.sleep(0.4)
    _ = last_err  # swallow; caller will fall through to next cascade tier
    return False


def _fetch_text(url: str, timeout: float = 10.0, max_bytes: int = 200_000) -> str:
    """GET `url` and return up to `max_bytes` of decoded text. Empty on failure."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(max_bytes)
            if resp.getheader("Content-Encoding") == "gzip":
                try:
                    raw = gzip.decompress(raw)
                except OSError:
                    pass  # truncated gzip; the head we already have may suffice
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError, OSError):
        return ""


# ---------- Clearbit Autocomplete ----------

def clearbit_suggest(name: str, timeout: float = 6.0) -> tuple[str, str] | None:
    """Return (domain, returned_name) for the top Clearbit autocomplete hit."""
    if not name:
        return None
    try:
        q = urllib.parse.quote(name)
        url = f"https://autocomplete.clearbit.com/v1/companies/suggest?query={q}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if resp.getheader("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            data = json.loads(raw.decode("utf-8", errors="replace"))
        if not data:
            return None
        top = data[0]
        domain = (top.get("domain") or "").strip().lower()
        ret = top.get("name") or ""
        return (domain, ret) if domain else None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ConnectionError,
            UnicodeDecodeError, OSError):
        return None


# ---------- HTML icon parsing ----------

_ICON_RELS = {"apple-touch-icon", "apple-touch-icon-precomposed", "icon", "shortcut icon", "mask-icon"}


class _IconExtractor(HTMLParser):
    """Tiny parser that captures candidate icon URLs from <head>.

    We stop walking once we hit </head> to avoid scanning the full body.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.icons: list[tuple[int, str]] = []  # (declared_size, href)
        self.og_image: str = ""
        self._done = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._done:
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "link":
            rel = a.get("rel", "").lower().strip()
            if rel in _ICON_RELS and a.get("href"):
                size = 0
                m = re.search(r"(\d+)x\d+", a.get("sizes", ""))
                if m:
                    size = int(m.group(1))
                elif "apple" in rel:
                    size = 180  # conventional apple-touch-icon resolution
                self.icons.append((size, a["href"]))
        elif tag == "meta":
            prop = (a.get("property") or a.get("name") or "").lower()
            if prop in ("og:image", "og:image:url", "twitter:image") and a.get("content"):
                self.og_image = self.og_image or a["content"]

    def handle_endtag(self, tag: str) -> None:
        if tag == "head":
            self._done = True


def parse_html_icons(page_url: str) -> str:
    """Return the highest-resolution icon URL declared in the page's <head>."""
    html = _fetch_text(page_url)
    if not html:
        return ""
    p = _IconExtractor()
    try:
        p.feed(html)
    except Exception:
        return ""
    # Prefer largest declared size; fall back to og:image when no <link icon>.
    if p.icons:
        size, href = max(p.icons, key=lambda t: t[0])
        return urllib.parse.urljoin(page_url, href)
    if p.og_image:
        return urllib.parse.urljoin(page_url, p.og_image)
    return ""


# ---------- source loading ----------

def load_entertainer_index() -> dict[str, str]:
    """Map normalized merchant name -> merchant_logo URL."""
    if not ENTERTAINER.exists():
        return {}
    rows = json.loads(ENTERTAINER.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for r in rows:
        key = normalize(r.get("merchant_name"))
        logo = r.get("merchant_logo")
        if key and logo and key not in out:
            out[key] = logo
    return out


def load_fazaa_index() -> dict[str, str]:
    """Map normalized partner name -> absolute partnerLogoUri.

    Skips entries whose logo path doesn't look like an image (e.g. some
    clinics store a .pdf brochure in `partnerLogoUri`). The HEAD check in
    the resolver would catch these anyway, but filtering up front saves
    network round-trips.
    """
    if not FAZAA.exists():
        return {}
    rows = json.loads(FAZAA.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for r in rows:
        partner = ((r.get("detail") or {}).get("partner") or {})
        name = partner.get("partnerName") or r.get("partnerName")
        path = partner.get("partnerLogoUri") or ""
        key = normalize(name)
        if not key or not path:
            continue
        # Drop obvious non-image payloads stored in the logo slot.
        if path.lower().endswith((".pdf", ".doc", ".docx", ".zip")):
            continue
        # Fazaa uses /upload/partners/no-partner.png as the literal "no logo"
        # placeholder. Skip — the HEAD validator would catch it anyway, but
        # filtering up front spares 100+ wasted round-trips per run.
        if path.endswith("/no-partner.png") or path == "no-partner.png":
            continue
        # Fazaa stores some logos with spaces or other unsafe characters in
        # the filename. Percent-encode the path so urllib can issue requests.
        if not path.startswith("http"):
            safe_path = urllib.parse.quote(path, safe="/:%")
            url = f"{FAZAA_CDN}{safe_path}"
        else:
            url = path
        if key not in out:
            out[key] = url
    return out


def load_playbook_index() -> dict[str, tuple[str, str]]:
    """Map normalized venue name -> (website_url, first_image_url)."""
    if not PLAYBOOK.exists():
        return {}
    rows = json.loads(PLAYBOOK.read_text(encoding="utf-8"))
    out: dict[str, tuple[str, str]] = {}
    for r in rows:
        key = normalize(r.get("Name") or r.get("VenueName"))
        if not key:
            continue
        site = ((r.get("detail") or {}).get("WebsiteUrl") or "").strip()
        imgs = r.get("Images") or []
        first_img = imgs[0] if imgs else ""
        if key not in out:
            out[key] = (site, first_img)
    return out


# ---------- the cascade ----------

def resolve_one(row: dict, ent_idx: dict[str, str], fz_idx: dict[str, str],
                pb_idx: dict[str, tuple[str, str]],
                use_clearbit: bool, use_html: bool) -> dict:
    out = dict(row)
    out.update({
        "suggested_website": "",
        "suggested_logo_url": "",
        "source": "none",
        "confidence": "none",
        "validation_status": "untested",
        "notes": "",
    })
    key = normalize(row.get("name"))
    name = row.get("name", "")

    # 1) Entertainer merchant_logo - direct CDN URL, brand-curated.
    if key in ent_idx:
        logo = ent_idx[key]
        if head_image_ok(logo):
            out.update(
                suggested_logo_url=logo,
                source="entertainer",
                confidence="high",
                validation_status="ok",
            )
            return out
        out["notes"] = "entertainer match found but logo HEAD failed"

    # 2) Fazaa partnerLogoUri - direct image from Fazaa's CDN. Similar
    # confidence to Entertainer (brand-curated), but quality varies more
    # (some partners upload storefront photos instead of clean logos).
    if key in fz_idx:
        logo = fz_idx[key]
        if head_image_ok(logo):
            out.update(
                suggested_logo_url=logo,
                source="fazaa",
                confidence="high",
                validation_status="ok",
            )
            return out
        prev = out.get("notes") or ""
        out["notes"] = f"{prev}; fazaa match found but logo HEAD failed".lstrip("; ")

    # 3) Playbook - prefer detail.WebsiteUrl as a domain hint.
    if key in pb_idx:
        site, _img = pb_idx[key]
        domain = _extract_domain(site)
        if domain:
            out["suggested_website"] = f"https://{domain}"
            cand = f"https://icon.horse/icon/{domain}"
            if head_image_ok(cand):
                out.update(
                    suggested_logo_url=cand,
                    source="playbook",
                    confidence="medium",
                    validation_status="ok",
                )
                return out

    # 4) Clearbit Autocomplete - free-text brand -> domain.
    if use_clearbit and not row.get("has_website"):
        sugg = clearbit_suggest(name)
        if sugg:
            domain, returned = sugg
            same = normalize(returned) == key
            out["suggested_website"] = f"https://{domain}"
            cand = f"https://icon.horse/icon/{domain}"
            if head_image_ok(cand):
                out.update(
                    suggested_logo_url=cand,
                    source="clearbit_autocomplete",
                    confidence="high" if same else "low",
                    validation_status="ok",
                    notes="" if same else f"name mismatch: '{returned}' vs '{name}'",
                )
                return out

    # 5) HTML parse of existing website (for places that have one).
    if use_html and row.get("has_website"):
        parsed = parse_html_icons(row["website"])
        if parsed and head_image_ok(parsed):
            out.update(
                suggested_logo_url=parsed,
                source="html_parse",
                confidence="medium",
                validation_status="ok",
            )
            return out

    # 6) icon.horse fallback when we have *any* domain.
    fallback_domain = _extract_domain(out["suggested_website"]) or row.get("logo_domain") or ""
    if fallback_domain:
        cand = f"https://icon.horse/icon/{fallback_domain}"
        if head_image_ok(cand):
            out.update(
                suggested_logo_url=cand,
                source="icon_horse",
                confidence="low",
                validation_status="ok",
                notes=out.get("notes") or "generic-favicon fallback",
            )
            return out

    return out


# ---------- main ----------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, default=None, help="resolve only the first N rows")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--no-clearbit", action="store_true", help="skip the Clearbit Autocomplete tier")
    parser.add_argument("--no-html", action="store_true", help="skip the HTML icon-parse tier")
    parser.add_argument("--only-missing", action="store_true",
                        help="process only rows where has_website is False")
    args = parser.parse_args()

    if not AUDIT.exists():
        print(f"audit file not found: {AUDIT}\nRun audit_place_icons.py first.", file=sys.stderr)
        return 2

    audit_rows = json.loads(AUDIT.read_text(encoding="utf-8"))
    if args.only_missing:
        audit_rows = [r for r in audit_rows if not r.get("has_website")]
    if args.limit:
        audit_rows = audit_rows[: args.limit]

    print(f"loading source indexes...")
    ent_idx = load_entertainer_index()
    fz_idx = load_fazaa_index()
    pb_idx = load_playbook_index()
    print(f"  entertainer brands: {len(ent_idx)}")
    print(f"  fazaa partners:     {len(fz_idx)}")
    print(f"  playbook venues:    {len(pb_idx)}")
    print(f"resolving {len(audit_rows)} places with {args.workers} workers...")

    resolved: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(resolve_one, r, ent_idx, fz_idx, pb_idx,
                               not args.no_clearbit, not args.no_html) for r in audit_rows]
        for i, fut in enumerate(cf.as_completed(futures), start=1):
            resolved.append(fut.result())
            if i % 100 == 0 or i == len(audit_rows):
                print(f"  {i}/{len(audit_rows)}", file=sys.stderr)

    # Re-sort by id so output ordering is stable across runs.
    resolved.sort(key=lambda r: r["id"])
    DEST.write_text(json.dumps(resolved, ensure_ascii=False, indent=2), encoding="utf-8")

    by_source: dict[str, int] = {}
    for r in resolved:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    total = len(resolved)
    print(f"\nwrote {DEST}")
    print(f"  total resolved rows: {total}")
    for src in ("entertainer", "fazaa", "playbook", "clearbit_autocomplete", "html_parse", "icon_horse", "none"):
        n = by_source.get(src, 0)
        pct = n * 100 // total if total else 0
        print(f"  {src:<22} {n:>5} ({pct}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
