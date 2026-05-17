"""Probe Zomato per-restaurant pages and extract their visible dining offers.

For each candidate `(name, zomato_slug)` pair, fetches
`https://www.zomato.com/dubai/{slug}/info`, parses the
`SECTION_DINING_OFFERS_V2` block from the SSR'd `__PRELOADED_STATE__`,
and emits one row per offer it finds.

We're after offers that fit our model — flat % off / fixed AED off /
BOGO — and explicitly skip:

  - PRE-BOOK OFFERS (require booking via Zomato app; not actionable
    for our users who walk in)
  - SURPRISE / scratch-card cashback (probabilistic, Zomato-Wallet
    only, not a flat discount)
  - BANK OFFERS (per-card; already covered by our bank source-program
    skills if applicable)

What we KEEP: INSTANT OFFERS — `offerType: dining_gold` with a
`No booking required` subtitle and a clear `offer_value`. These are
the universal Zomato Gold flat discounts.

Output: data/zomato_offers_enriched.json — one row per (place, offer)
that should be ingested. Failures (404s, network errors, no offers
found) are reported but don't kill the run.
"""
from __future__ import annotations

import concurrent.futures as cf
import gzip
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "data" / "zomato_offers_enriched.json"

# Candidate set: combines the 25 already-seeded Gold venues + Hamptons +
# ~25 well-known popular Dubai restaurants. The slug guesses are
# best-effort; the probe reports failures so we can iterate.
# (display_name, area, zomato_slug)
CANDIDATES: list[tuple[str, str, str]] = [
    # ===== Already in the Gold seed (0036_zomato_gold_seed.py) =====
    ("Applebee's",                "Dubai Festival City",     "applebees-1-dubai-festival-city"),
    ("Azure Pool Bar",            "Jumeirah Beach Residence","azure-pool-bar-sheraton-jumeirah-beach-resort-jumeirah-beach-residence"),
    ("Channels",                  "Barsha Heights",          "channels-radisson-blu-barsha-heights-barsha-heights"),
    ("Cilantro",                  "Dubai Media City",        "cilantro-arjaan-by-rotana-dubai-media-city"),
    ("DXBlends",                  "Umm Hurair",              "dxblends-umm-hurair"),
    ("IHOP",                      "Dubai Festival City",     "ihop-dubai-festival-city"),
    ("Pawar Family Restaurant",   "International City",      "pawar-family-restaurant-international-city"),
    ("Ramzin Cafe",               "Hor Al Anz",              "ramzin-cafe-1-hor-al-anz"),
    ("WOFL",                      "Jumeirah Beach Residence","wofl-jumeirah-beach-residence"),
    ("Kaftan Turkish Cuisine & Fine Art", "Business Bay",    "kaftan-turkish-cuisine-fine-art-business-bay"),
    ("Wakame",                    "Downtown Dubai",          "wakame-sofitel-dubai-downtown"),
    ("Intersect by Lexus",        "DIFC",                    "intersect-by-lexus-difc"),
    ("Gaucho",                    "DIFC",                    "gaucho-difc"),
    ("Leopold's of London",       "Downtown Dubai",          "leopolds-of-london-downtown-dubai"),
    ("Art House Cafe",            "Jumeirah",                "art-house-cafe-jumeirah"),
    ("Bubo Barcelona Cafe",       "Downtown Dubai",          "bubo-barcelona-cafe-downtown-dubai"),
    ("Cafe Mandarina",            "Downtown Dubai",          "cafe-mandarina-downtown-dubai"),
    ("Crumbs Elysee",             "Downtown Dubai",          "crumbs-elysee-downtown-dubai"),
    ("Treej Cafe",                "Dubai Hills",             "treej-cafe-dubai-hills"),
    ("Mitts & Trays",             "Jumeirah",                "mitts-trays-jumeirah"),
    ("Al Sultan Restaurant & Grill", "Deira",                "al-sultan-restaurant-and-grill-deira"),
    ("Five Guys",                 "Dubai Mall",              "five-guys-the-dubai-mall-downtown-dubai"),
    ("Pizza Di Rocco",            "Jumeirah Lake Towers",    "pizza-di-rocco-jumeirah-lake-towers"),
    ("At.mosphere",               "Downtown Dubai",          "atmosphere-burj-khalifa-downtown-dubai"),
    ("Trèsind",                   "Sheikh Zayed Road",       "tresind-nassima-royal-hotel-sheikh-zayed-road"),

    # ===== User-requested =====
    ("The Hamptons Cafe",         "Jumeirah Islands",        "the-hamptons-cafe-emirates-hills"),
    ("The Hamptons Cafe (Umm Suqeim)", "Umm Suqeim",         "the-hamptons-cafe-umm-suqeim"),

    # ===== Well-known popular Dubai venues (slugs are best-effort) =====
    ("Couqley French Bistro",     "JLT",                     "couqley-french-bistro-and-bar-jumeirah-lake-towers-jlt"),
    ("Asia Asia",                 "Pier 7",                  "asia-asia-pier-7-dubai-marina"),
    ("BB Social Dining",          "DIFC",                    "bb-social-dining-difc"),
    ("Catch 22",                  "JLT",                     "catch-22-jumeirah-lake-towers-jlt"),
    ("Cipriani",                  "DIFC",                    "cipriani-difc"),
    ("Stoked",                    "Dubai Hills",             "stoked-dubai-hills"),
    ("Coya",                      "Four Seasons Resort, Jumeirah", "coya-four-seasons-resort-dubai-jumeirah"),
    ("Karma Kafé",                "Souk Al Bahar",           "karma-kafe-by-buddha-bar-souk-al-bahar-downtown-dubai"),
    ("Tribes Carnivore Restaurant", "Mall of the Emirates",  "tribes-carnivore-restaurant-mall-of-the-emirates-al-barsha"),
    ("Carine",                    "Emirates Golf Club",      "carine-emirates-golf-club-al-sufouh"),
    ("Buddha-Bar",                "Grosvenor House",         "buddha-bar-grosvenor-house-dubai-marina"),
    ("Pierchic",                  "Al Qasr",                 "pierchic-al-qasr-madinat-jumeirah-umm-suqeim"),
    ("La Petite Maison",          "DIFC",                    "la-petite-maison-difc"),
    ("Galvin",                    "DIFC",                    "galvin-difc"),
    ("STK Steakhouse",            "Downtown Dubai",          "stk-steakhouse-double-tree-by-hilton-business-bay"),
    ("Eat Greek Kouzina",         "Mall of the Emirates",    "eat-greek-kouzina-mall-of-the-emirates-al-barsha"),
    ("Tomo",                      "Raffles Dubai",           "tomo-raffles-dubai-wafi"),
    ("Black Tap",                 "Jumeirah Beach Hotel",    "black-tap-jumeirah-beach-hotel-umm-suqeim"),
    ("Kaftan Turkish Cuisine",    "Al Quoz",                 "kaftan-al-quoz"),
    ("Reform Social & Grill",     "The Lakes",               "reform-social-and-grill-the-lakes"),
    ("Akiba Dori",                "Dubai Hills",             "akiba-dori-dubai-hills"),
    ("Ninive",                    "Emirates Towers",         "ninive-emirates-towers-trade-centre-2"),
    ("Hutong",                    "DIFC",                    "hutong-difc"),
    ("Maiz Tacos",                "Dubai Marina",            "maiz-tacos-dubai-marina"),
    ("Risen Cafe",                "Al Quoz",                 "risen-cafe-al-quoz"),
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
PAGE_TIMEOUT = 12


def _fetch(slug: str) -> tuple[bytes | None, int]:
    url = f"https://www.zomato.com/dubai/{slug}"
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip",
    })
    try:
        with urllib.request.urlopen(req, timeout=PAGE_TIMEOUT) as r:
            body = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return body, r.status
    except urllib.error.HTTPError as e:
        return None, e.code
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, 0


def _extract_offers(html: bytes) -> list[dict]:
    """Return the SECTION_DINING_OFFERS_V2.offers list, or []."""
    try:
        text = html.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return []
    m = re.search(r"window\.__PRELOADED_STATE__\s*=\s*(.+?);\s*</script>", text, re.DOTALL)
    if not m:
        return []
    raw = m.group(1).strip()
    if not raw.startswith("JSON.parse("):
        return []
    inner = raw[len("JSON.parse("):-1].strip()
    try:
        data = json.loads(json.loads(inner))
    except (json.JSONDecodeError, ValueError):
        return []
    rest = data.get("pages", {}).get("restaurant", {}) or {}
    if not rest:
        return []
    rid = next(iter(rest))
    sec = rest[rid].get("sections", {}).get("SECTION_DINING_OFFERS_V2", {}) or {}
    return sec.get("offers") or []


def classify_offer(raw_offer: dict) -> dict | None:
    """Map a Zomato offer to our normalized shape, or None if we should skip it.

    Keep:
      - INSTANT OFFER  (offerType=dining_gold, "No booking required" in subtitle) — flat %
      - "Buy 1 Get 1" / BOGO mechanics
    Skip:
      - PRE-BOOK OFFER (booking via Zomato required)
      - SURPRISE / cashback scratch cards
      - BANK OFFER
    """
    heading = (raw_offer.get("heading") or "").upper().strip()
    subtitle = (raw_offer.get("subtitle") or "").lower()
    title = (raw_offer.get("title") or "").strip()
    offer_type = raw_offer.get("offerType") or ""
    offer_value = raw_offer.get("offer_value")
    details = raw_offer.get("offerDetails") or {}

    # Skip non-actionable offer types
    if offer_type in ("cashback", "bank_offer"):
        return None
    if heading == "PRE-BOOK OFFER" or "booking required" in subtitle and "no booking required" not in subtitle:
        return None

    # Detect BOGO from title text
    if re.search(r"\bbuy\s*(?:1|one)\s*get\s*(?:1|one)\b.{0,30}\bfree\b", title, re.IGNORECASE) or \
       re.search(r"\b(2|two)[\s\-]*for[\s\-]*(1|one)\b", title, re.IGNORECASE):
        return {
            "discount_type": "bogo",
            "title": title,
            "subtitle": raw_offer.get("subtitle"),
            "offer_type_zomato": offer_type,
            "heading": heading,
        }

    # Flat percentage — derive from offer_value or offerDetails.offerVal
    pct = None
    if isinstance(offer_value, (int, float)) and 1 <= offer_value <= 99:
        pct = int(offer_value)
    elif isinstance(details, dict):
        val = details.get("offerVal")
        if isinstance(val, (int, float)) and 1 <= val <= 99:
            pct = int(val)
    if pct is not None:
        return {
            "discount_type": "percentage",
            "percentage": pct,
            "title": title,
            "subtitle": raw_offer.get("subtitle"),
            "offer_type_zomato": offer_type,
            "heading": heading,
        }

    return None


def probe_one(idx: int, name: str, area: str, slug: str) -> dict:
    body, status = _fetch(slug)
    if body is None:
        return {"idx": idx, "name": name, "area": area, "slug": slug,
                "status": status, "offers": [], "error": f"http_{status}"}
    offers_raw = _extract_offers(body)
    classified = [c for c in (classify_offer(o) for o in offers_raw) if c]
    return {
        "idx": idx, "name": name, "area": area, "slug": slug,
        "status": status,
        "url": f"https://www.zomato.com/dubai/{slug}",
        "offers_raw_count": len(offers_raw),
        "offers": classified,
    }


def main():
    print(f"Probing {len(CANDIDATES)} candidate venues (concurrency=6)…")
    t0 = time.monotonic()
    results: list[dict] = [None] * len(CANDIDATES)  # type: ignore[assignment]
    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(probe_one, i, name, area, slug): i
            for i, (name, area, slug) in enumerate(CANDIDATES)
        }
        for fut in cf.as_completed(futures):
            i = futures[fut]
            results[i] = fut.result()
            r = results[i]
            tag = "OK " if r["offers"] else ("ERR" if r.get("error") else "—  ")
            marks = ",".join(
                f"{o['discount_type']}{':' + str(o.get('percentage')) if o.get('percentage') else ''}"
                for o in r["offers"]
            ) or (r.get("error") or "(no offers parsed)")
            print(f"  {tag} [{i:2d}] {r['name'][:38]:<38} {marks}")

    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {len(results)} probe rows ({time.monotonic()-t0:.0f}s) -> {DEST.relative_to(ROOT)}")
    # Summary
    with_offer = sum(1 for r in results if r["offers"])
    errors = sum(1 for r in results if r.get("error"))
    print(f"  venues with at least one keepable offer: {with_offer}")
    print(f"  venues with HTTP/parse error:            {errors}")


if __name__ == "__main__":
    main()
