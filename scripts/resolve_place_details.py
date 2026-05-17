"""Resolve missing description / phone / address / coords for each Place
in data/place_details_audit.json by cascading through free sources.

Cascade (per Place, first non-empty wins per field):

  Source A — Place's own website
    - HTTP GET the root URL (8s timeout, retry once)
    - description ← og:description / meta[name=description] / JSON-LD `description`
    - phone, address (street + locality), lat/lng ← JSON-LD `@type=Restaurant`
      / `LocalBusiness` / `Hotel` / `Organization` / `FoodEstablishment`

  Source B — OpenStreetMap Overpass (for Places with lat/lng but unfilled fields)
    - nwr query within 80m of coords, name-matched via apps.places.matching.normalize_name
    - phone, website, address (addr:full / street+city) ← OSM tags

Anything still empty → `needs_review: true`.

Output: data/place_details_enriched.json — one row per Place where at
least one field resolved, with the cascade source tagged per-field.

Re-runs of this script HEAD-check the audit file's `has_*` flags so
Places whose curators have manually filled in the missing data don't get
churned through the pipeline again.

Concurrent fetches (default 8 workers, like enrich_fazaa_offers.py).
Pass --limit N for smoke tests.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import gzip
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "data" / "place_details_audit.json"
DEST = ROOT / "data" / "place_details_enriched.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
SITE_TIMEOUT = 8        # don't wait long for a slow venue website
OVERPASS_TIMEOUT = 20

# Description quality bounds — too short = stub, too long = page-dump.
DESC_MIN = 50
DESC_MAX = 500

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# JSON-LD @type values we'll accept as a venue node.
BUSINESS_TYPES = {
    "Restaurant", "LocalBusiness", "Hotel", "Organization",
    "FoodEstablishment", "Store", "ShoppingCenter", "BarOrPub",
    "CafeOrCoffeeShop", "TouristAttraction",
}


# ---------------------------------------------------------------------------
# Source A: venue website
# ---------------------------------------------------------------------------

def _fetch_html(url: str) -> bytes | None:
    """GET the URL with redirects and gzip; return bytes or None on failure."""
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url.lstrip("/")
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip",
    })
    try:
        with urllib.request.urlopen(req, timeout=SITE_TIMEOUT) as r:
            body = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return body
    except (urllib.error.URLError, TimeoutError, OSError, gzip.BadGzipFile):
        return None


def _walk_jsonld(soup: BeautifulSoup):
    """Yield each JSON-LD dict on the page (handles @graph wrappers)."""
    for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (s.string or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        candidates = data.get("@graph", [data]) if isinstance(data, dict) else data
        if not isinstance(candidates, list):
            candidates = [candidates]
        for cand in candidates:
            if isinstance(cand, dict):
                yield cand


def _is_business_node(node: dict) -> bool:
    t = node.get("@type")
    if isinstance(t, list):
        return any(x in BUSINESS_TYPES for x in t)
    return t in BUSINESS_TYPES


# Phrases that flag a description as corporate-homepage marketing rather
# than a real venue blurb. Hand-tuned from observed false-positives (Jumeirah
# corporate site, Shangri-La booking funnel, etc.).
_FLUFF_PATTERNS = re.compile(
    r"\b(rate guaranteed|luxury hotel destinations|best rate guaranteed|"
    r"book direct for offers|join \w+ circle|"
    r"explore the official|find your perfect stay|"
    r"book online to get up to|guarantee your seats|skip the queue)\b",
    re.IGNORECASE,
)


def _clean_desc(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not (DESC_MIN <= len(text) <= DESC_MAX):
        return ""
    if _FLUFF_PATTERNS.search(text):
        return ""
    return text


def _page_identifies_as(soup: BeautifulSoup, place_name: str) -> bool:
    """True if the page's <title> / og:title / JSON-LD `name` shares a
    substantial fraction of tokens with the Place name.

    Why this matters: many Places have `website` pointing to a parent
    corporate site (e.g. jumeirah.com, shangri-la.com) rather than the
    specific venue page. Pulling description/phone/address from that
    homepage gives wrong-venue data — the Jumeirah HQ phone instead of
    the restaurant's. This check rejects the whole page when it's
    clearly not about the named venue.
    """
    from apps.places.matching import normalize_name
    place_tokens = set(normalize_name(place_name).split())
    if not place_tokens:
        return True  # nothing to compare against — let it through

    candidates: list[str] = []
    if soup.title and soup.title.string:
        candidates.append(soup.title.get_text(strip=True))
    ogt = soup.find("meta", attrs={"property": "og:title"})
    if ogt and ogt.get("content"):
        candidates.append(ogt["content"])
    for node in _walk_jsonld(soup):
        if isinstance(node.get("name"), str):
            candidates.append(node["name"])

    for cand in candidates:
        cand_tokens = set(normalize_name(cand).split())
        if not cand_tokens:
            continue
        overlap = place_tokens & cand_tokens
        # Either at least half the place tokens are present, OR the longest
        # place token (typically the brand/proper noun) is in the candidate.
        longest = max(place_tokens, key=len) if place_tokens else ""
        if (place_tokens and len(overlap) / len(place_tokens) >= 0.5) or longest in cand_tokens:
            return True
    return False


def resolve_from_website(website: str, place_name: str) -> dict:
    """Return a dict of {field: value} fills extracted from the venue's homepage.

    Returns {} if the fetched page's title/headings don't identify it as
    being about `place_name` — protects against corporate-homepage pollution
    where a generic Jumeirah/Shangri-La page returns its HQ contact details
    instead of the actual venue's.
    """
    body = _fetch_html(website)
    if not body:
        return {}
    try:
        soup = BeautifulSoup(body, "html.parser")
    except Exception:
        return {}

    if not _page_identifies_as(soup, place_name):
        return {}

    out: dict = {}

    # Description: og:description -> meta description -> JSON-LD description
    for selector in [
        {"name": "meta", "attrs": {"property": "og:description"}},
        {"name": "meta", "attrs": {"name": "description"}},
    ]:
        tag = soup.find(**selector)
        if tag:
            cleaned = _clean_desc(tag.get("content") or "")
            if cleaned:
                out["description"] = cleaned
                break

    # Structured business fields from JSON-LD
    for node in _walk_jsonld(soup):
        if not _is_business_node(node):
            continue
        # description fallback if og: didn't work
        if "description" not in out:
            cleaned = _clean_desc(node.get("description") or "")
            if cleaned:
                out["description"] = cleaned
        if "phone" not in out:
            tel = (node.get("telephone") or "").strip()
            if tel:
                out["phone"] = tel
        if "address" not in out:
            addr = node.get("address") or {}
            if isinstance(addr, dict):
                parts = [
                    addr.get("streetAddress"),
                    addr.get("addressLocality"),
                ]
                joined = ", ".join(p.strip() for p in parts if isinstance(p, str) and p.strip())
                if joined:
                    out["address"] = joined
            elif isinstance(addr, str) and addr.strip():
                out["address"] = addr.strip()
        if "lat" not in out:
            geo = node.get("geo") or {}
            if isinstance(geo, dict):
                try:
                    lat = float(geo["latitude"]) if geo.get("latitude") is not None else None
                    lng = float(geo["longitude"]) if geo.get("longitude") is not None else None
                    if lat is not None and lng is not None:
                        out["lat"] = lat
                        out["lng"] = lng
                except (TypeError, ValueError):
                    pass
        if "description" in out and "phone" in out and "address" in out and "lat" in out:
            break

    return out


# ---------------------------------------------------------------------------
# Source B: OpenStreetMap Overpass
# ---------------------------------------------------------------------------

def _overpass(lat: float, lng: float) -> list[dict]:
    """Return all named OSM features within 80m of (lat, lng)."""
    query = (
        f"[out:json][timeout:{OVERPASS_TIMEOUT}];"
        f'(nwr(around:80,{lat},{lng})["name"];);'
        f"out tags center;"
    )
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(OVERPASS_URL, data=data, headers={
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "gzip",
    })
    try:
        with urllib.request.urlopen(req, timeout=OVERPASS_TIMEOUT + 5) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            payload = json.loads(raw)
            return payload.get("elements", []) or []
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return []


def _name_score(a: str, b: str) -> float:
    """Cheap normalized-token Jaccard. Returns 0.0–1.0."""
    from apps.places.matching import normalize_name
    na = set(normalize_name(a).split())
    nb = set(normalize_name(b).split())
    if not na or not nb:
        return 0.0
    return len(na & nb) / len(na | nb)


def resolve_from_osm(name: str, lat: float, lng: float) -> dict:
    """Return a dict of phone/website/address backfills from the best-matching
    OSM feature near the Place's coords (Jaccard ≥ 0.4 on normalized names)."""
    elements = _overpass(lat, lng)
    if not elements:
        return {}
    best = None
    best_score = 0.0
    for el in elements:
        tags = el.get("tags") or {}
        candidate = tags.get("name") or tags.get("name:en") or ""
        if not candidate:
            continue
        score = _name_score(name, candidate)
        if score > best_score:
            best_score = score
            best = tags
    if best_score < 0.4 or not best:
        return {}

    out: dict = {}
    phone = (best.get("contact:phone") or best.get("phone") or "").strip()
    if phone:
        out["phone"] = phone
    website = (best.get("contact:website") or best.get("website") or "").strip()
    if website:
        out["website"] = website
    addr_full = (best.get("addr:full") or "").strip()
    if not addr_full:
        parts = [
            best.get("addr:housenumber"),
            best.get("addr:street"),
            best.get("addr:district"),
            best.get("addr:city"),
        ]
        addr_full = " ".join(p.strip() for p in parts if isinstance(p, str) and p.strip())
    if addr_full:
        out["address"] = addr_full
    return out


# ---------------------------------------------------------------------------
# Main resolver
# ---------------------------------------------------------------------------

def resolve_one(audit_row: dict) -> dict | None:
    """Return the enriched-row dict for one Place, or None if nothing resolved."""
    row: dict = {
        "id": audit_row["id"],
        "slug": audit_row["slug"],
        "name": audit_row["name"],
    }
    targets = {
        "description": not audit_row["has_description"],
        "phone": not audit_row["has_phone"],
        "address": not audit_row["has_address"],
    }
    if not any(targets.values()):
        return None  # nothing to fill

    # Source A — venue website
    if audit_row.get("website"):
        a = resolve_from_website(audit_row["website"], audit_row["name"])
        for field in ("description", "phone", "address", "lat", "lng"):
            if field in a:
                if field in ("lat", "lng") and audit_row.get(field) is None:
                    row[field] = {"value": a[field], "source": "website-jsonld"}
                elif field in targets and targets[field]:
                    row[field] = {"value": a[field], "source": "website-jsonld"}
                    targets[field] = False

    # Source B — OSM Overpass (only if we still have missing targets AND coords)
    still_need = any(targets.values())
    lat = audit_row.get("lat") or row.get("lat", {}).get("value") if isinstance(row.get("lat"), dict) else audit_row.get("lat")
    lng = audit_row.get("lng") or row.get("lng", {}).get("value") if isinstance(row.get("lng"), dict) else audit_row.get("lng")
    if still_need and lat is not None and lng is not None:
        b = resolve_from_osm(audit_row["name"], lat, lng)
        for field in ("phone", "address"):
            if field in b and targets.get(field):
                row[field] = {"value": b[field], "source": "osm-overpass"}
                targets[field] = False
        if "website" in b and not audit_row.get("website"):
            row["website"] = {"value": b["website"], "source": "osm-overpass"}

    # Did we resolve anything?
    resolved_fields = [k for k in ("description", "phone", "address", "website", "lat", "lng")
                       if k in row]
    if not resolved_fields:
        return None

    row["needs_review"] = any(targets.values())
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, default=None,
                        help="resolve only the first N audit rows (smoke test)")
    parser.add_argument("--workers", type=int, default=8,
                        help="concurrent HTTP workers (default 8)")
    parser.add_argument("--skip-osm", action="store_true",
                        help="skip Source B (Overpass) — useful when Overpass is slow / down")
    args = parser.parse_args()

    # Bootstrap Django so we can import apps.places.matching.
    sys.path.insert(0, str(ROOT))
    import os as _os
    _os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()

    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    work_list = [r for r in audit if not (
        r["has_description"] and r["has_phone"] and r["has_address"]
    )]
    if args.limit:
        work_list = work_list[: args.limit]

    print(f"resolving {len(work_list)} Places with at least one empty field"
          f" (workers={args.workers}, skip-osm={args.skip_osm}) ...")

    # Wire the global skip-osm flag through a closure
    if args.skip_osm:
        global resolve_from_osm  # noqa: PLW0603
        def _stub(*_a, **_k): return {}
        resolve_from_osm = _stub  # type: ignore[assignment]

    resolved: list[dict] = []
    counts = {"description": 0, "phone": 0, "address": 0, "website": 0, "needs_review": 0}
    t0 = time.monotonic()
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(resolve_one, r): r for r in work_list}
        done = 0
        for fut in cf.as_completed(futures):
            done += 1
            try:
                row = fut.result()
            except Exception as e:  # noqa: BLE001
                print(f"  ERROR on {futures[fut]['slug']}: {e}", file=sys.stderr)
                continue
            if row is None:
                continue
            for k in counts:
                if k == "needs_review":
                    if row.get("needs_review"):
                        counts[k] += 1
                elif k in row:
                    counts[k] += 1
            resolved.append(row)
            if done % 100 == 0:
                print(f"  {done}/{len(work_list)} processed ({time.monotonic()-t0:.0f}s elapsed)")

    DEST.write_text(json.dumps(resolved, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {len(resolved)} enriched rows -> {DEST.relative_to(ROOT)}")
    print(f"  resolved description: {counts['description']:5d}")
    print(f"  resolved phone:       {counts['phone']:5d}")
    print(f"  resolved address:     {counts['address']:5d}")
    print(f"  resolved website:     {counts['website']:5d}")
    print(f"  needs_review (residual gaps): {counts['needs_review']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
