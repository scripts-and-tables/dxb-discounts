"""Parse the per-venue HTML fetched by fetch_atlantis_circle.py into the
enriched JSON that ingest_offers consumes.

Each Atlantis dining page carries a clean `<script type="application/ld+json">`
Restaurant block with name, address, lat/lng, telephone, cuisine, image,
and description. That's our data source — much more stable than scraping
freeform HTML.

The 20-venue inventory and the URL-segment → Place.slug mapping is
hard-coded (mirrors apps/discounts/migrations/0026_atlantis_circle_venues.py)
because:
  (a) the dining listing page is a JS-rendered SPA, so we can't discover
      venues from the live HTML, and
  (b) slug stability matters — re-deriving slugs from venue names would
      diverge from the seed and double up Places.

Tier percentages are also hard-coded (from migration 0020). The membership
page is a JS-rendered SPA and the tier table isn't in the HTML either.
If Atlantis changes its tier ladder, edit the TIERS dict below and re-run.

Output:
  data/atlantis_circle_enriched.json  (one row per venue, ingest input)
  data/atlantis_circle_tiers.json     (the tier table)
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from fetch_atlantis_circle import VENUES, PROBE_DIR  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# resort assignment + concise blurb per slug. Source-of-truth blurbs from
# migration 0026 — used as a fallback when the live page's JSON-LD
# description is empty or boilerplate.
VENUE_META: dict[str, dict] = {
    # Palm
    "hakkasan-atlantis-the-palm": {
        "name": "Hakkasan", "resort": "palm",
        "fallback_blurb": "MICHELIN-starred Cantonese restaurant at Atlantis, The Palm — premium dim sum, stir-fries and signature cocktails by Chef Andy Toh.",
    },
    "ossiano": {
        "name": "Ossiano", "resort": "palm",
        "fallback_blurb": "Dubai's one-MICHELIN-star underwater fine-dining restaurant at Atlantis, The Palm — degustation menu with floor-to-ceiling aquarium views.",
    },
    "saffron-atlantis": {
        "name": "Saffron", "resort": "palm",
        "fallback_blurb": "Pan-Asian buffet at Atlantis, The Palm with 220 dishes across 20+ live cooking stations — dim sum, stir-fries, curries, sushi.",
    },
    "kaleidoscope": {
        "name": "Kaleidoscope", "resort": "palm",
        "fallback_blurb": "International buffet at Atlantis, The Palm with Arabic, Asian and continental specialties across multiple live stations.",
    },
    "wavehouse": {
        "name": "Wavehouse", "resort": "palm",
        "fallback_blurb": "Family casual at Atlantis, The Palm — bowling, arcade games, and a menu of burgers, pizzas, wings and shakes.",
    },
    "gordon-ramsay-bread-street-kitchen": {
        "name": "Gordon Ramsay Bread Street Kitchen", "resort": "palm",
        "fallback_blurb": "Modern British by Gordon Ramsay at Atlantis, The Palm — classic dishes, Sunday roast, lively bar.",
    },
    "street-pizza-atlantis": {
        "name": "Gordon Ramsay's Street Pizza", "resort": "palm",
        "fallback_blurb": "Endless pizza slices and drinks shaped by Gordon Ramsay's crowd-favourite flavours — at Atlantis, The Palm.",
    },
    "ayamna": {
        "name": "Ayamna", "resort": "palm",
        "fallback_blurb": "Lebanese restaurant at Atlantis, The Palm — warm mezze, chargrilled meats and seafood, time-honoured desserts.",
    },
    "seafire-steakhouse": {
        "name": "Seafire Steakhouse", "resort": "palm",
        "fallback_blurb": "New York-style steakhouse at Atlantis, The Palm — premium cuts, seafood and a curated wine list.",
    },
    "en-fuego": {
        "name": "En Fuego", "resort": "palm",
        "fallback_blurb": "Latin American restaurant at Atlantis, The Palm — Mexican classics, fajitas, margaritas and a vibrant bar.",
    },
    # Royal
    "dinner-by-heston-blumenthal": {
        "name": "Dinner by Heston Blumenthal", "resort": "royal",
        "fallback_blurb": "MICHELIN-starred contemporary British by Heston Blumenthal at Atlantis The Royal — historic British recipes reimagined (Meat Fruit, Tipsy Cake).",
    },
    "estiatorio-milos": {
        "name": "Estiatorio Milos", "resort": "royal",
        "fallback_blurb": "Authentic Greek seafood at Atlantis The Royal — fresh oysters, ceviches, tzatziki, with views over the resort fountains.",
    },
    "cloud22": {
        "name": "Cloud 22", "resort": "royal",
        "fallback_blurb": "Rooftop infinity-pool day club and bar at Atlantis The Royal — handcrafted cocktails and small plates 22 floors up.",
    },
    "the-royal-tearoom": {
        "name": "The Royal Tearoom", "resort": "royal",
        "fallback_blurb": "Lavish afternoon tea at Atlantis The Royal — curated pastries, sweet and savoury bites, premium teas.",
    },
    "arianas-persian-kitchen": {
        "name": "Ariana's Persian Kitchen", "resort": "royal",
        "fallback_blurb": "Modern Persian cuisine at Atlantis The Royal — saffron rice, kebabs, slow-cooked stews and traditional desserts.",
    },
    "jaleo-by-jose-andres": {
        "name": "Jaleo by José Andrés", "resort": "royal",
        "fallback_blurb": "Spanish tapas by Chef José Andrés at Atlantis The Royal — paella, sangria, jamón ibérico and an extensive Spanish wine list.",
    },
    "ling-ling-atlantis": {
        "name": "Ling Ling", "resort": "royal",
        "fallback_blurb": "Pan-Asian dining and lounge at Atlantis The Royal — Japanese, Thai, Vietnamese and Korean dishes with DJ-driven evenings.",
    },
    "nobu-by-the-beach": {
        "name": "Nobu by The Beach", "resort": "royal",
        "fallback_blurb": "Beachfront Nobu (Japanese-Peruvian) at Atlantis The Royal — private cabanas, signature black cod miso, sushi and cocktails.",
    },
    "gastronomy-atlantis": {
        "name": "Gastronomy", "resort": "royal",
        "fallback_blurb": "Breakfast and dinner buffet at Atlantis The Royal — global cuisine with live cooking and premium ingredients.",
    },
    "la-mar-by-gaston-acurio": {
        "name": "La Mar by Gastón Acurio", "resort": "royal",
        "fallback_blurb": "Peruvian seafood by Chef Gastón Acurio at Atlantis The Royal — ceviche, tiradito, anticucho, Novo-Andean specials.",
    },
}

PALM_ADDRESS = "Atlantis The Palm, Crescent Road, Palm Jumeirah, Dubai"
ROYAL_ADDRESS = "Atlantis The Royal, Crescent Road, Palm Jumeirah, Dubai"

# Tier table — values from migrations/0020_seed_new_programs_and_tiers.py.
# Hard-coded because the live membership page is a JS-rendered SPA with no
# tier data in the raw HTML. If Atlantis updates its ladder, edit here.
TIERS = [
    {"name": "Blue",   "threshold": "Free signup",
     "benefit": "15% off restaurants",                                                 "percentage": 15},
    {"name": "Silver", "threshold": "AED 12,000/year on dining",
     "benefit": "20% off restaurants + birthday credit",                               "percentage": 20},
    {"name": "Gold",   "threshold": "AED 25,000/year on dining",
     "benefit": "25% off restaurants + early-bird bookings + beach access perks",      "percentage": 25},
    {"name": "Black",  "threshold": "AED 40,000/year on dining",
     "benefit": "30% off restaurants + exclusive event invitations",                   "percentage": 30},
]


def _restaurant_jsonld(soup: BeautifulSoup) -> dict | None:
    """Return the first @type=Restaurant JSON-LD block, or None.

    Archive.org rewrites embedded URLs to wayback paths
    (https://web.archive.org/web/.../https://...) — we strip those before
    parsing so the JSON is clean.
    """
    for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (s.string or "").strip()
        if not raw:
            continue
        cleaned = re.sub(r"https://web\.archive\.org/web/\d+/", "", raw)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            continue
        # Some pages use @graph wrapping; check both shapes.
        candidates = data.get("@graph", [data]) if isinstance(data, dict) else data
        if not isinstance(candidates, list):
            candidates = [candidates]
        for cand in candidates:
            if isinstance(cand, dict) and cand.get("@type") == "Restaurant":
                return cand
    return None


def parse_venue(slug: str, url_segment: str, html: bytes) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    meta = VENUE_META[slug]
    resort = meta["resort"]
    fallback_blurb = meta["fallback_blurb"]
    fallback_name = meta["name"]
    default_address = ROYAL_ADDRESS if resort == "royal" else PALM_ADDRESS

    record: dict = {
        "slug": slug,
        "atlantis_url_segment": url_segment,
        "resort": resort,
        "external_url": f"https://www.atlantis.com/dubai/dining/{url_segment}",
        # `name` is always the curated value from VENUE_META — JSON-LD names
        # are riddled with SEO taglines ("Hakkasan Dubai: Fine Dining (Michelin
        # Star) Chinese Restaurant", "Seafire Steakhouse & Bar in Dubai") that
        # we don't want in the user-facing Place.name. The raw scraped value
        # lives in `name_from_source` so a future drift check can compare.
        "name": fallback_name,
        "name_from_source": "",
        "cuisine_blurb": "",
        "address": default_address,
        "phone": "",
        "lat": None,
        "lng": None,
        "image_url": "",
        "cuisine": "",
        "is_operational": True,  # parser can't tell; flag manually via skill report
        "source": "html-jsonld",
        "tier_percentages": {t["name"].lower(): t["percentage"] for t in TIERS},
    }

    rest = _restaurant_jsonld(soup)
    if rest is None:
        # JSON-LD missing — page may have been replaced or 404'd. Fall back to
        # migration-0026 metadata so we still emit a usable row.
        record["source"] = "fallback-seed"
        record["cuisine_blurb"] = fallback_blurb
        return record

    record["name_from_source"] = (rest.get("name") or "").strip()

    desc = (rest.get("description") or "").strip()
    record["cuisine_blurb"] = desc or fallback_blurb
    record["phone"] = (rest.get("telephone") or "").strip()
    record["cuisine"] = (rest.get("servesCuisine") or "").strip()
    record["image_url"] = (rest.get("image") or "").strip()

    addr = rest.get("address") or {}
    street = (addr.get("streetAddress") or "").strip()
    city = (addr.get("addressLocality") or "").strip()
    record["address"] = ", ".join(p for p in [street, city] if p) or default_address

    geo = rest.get("geo") or {}
    try:
        record["lat"] = float(geo["latitude"]) if geo.get("latitude") is not None else None
        record["lng"] = float(geo["longitude"]) if geo.get("longitude") is not None else None
    except (TypeError, ValueError):
        record["lat"] = record["lng"] = None

    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-missing", action="store_true",
                        help="don't error if HTML for some venues is missing — emit fallback rows instead")
    args = parser.parse_args()

    DATA.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    missing: list[str] = []
    sources = {"html-jsonld": 0, "fallback-seed": 0}

    for url_segment, slug in VENUES:
        html_path = PROBE_DIR / f"{slug}.html"
        if not html_path.exists():
            missing.append(slug)
            if not args.allow_missing:
                continue
            # Synthesize a fallback row
            rec = parse_venue(slug, url_segment, b"")
            rows.append(rec)
            sources[rec["source"]] += 1
            continue
        html = html_path.read_bytes()
        rec = parse_venue(slug, url_segment, html)
        rows.append(rec)
        sources[rec["source"]] += 1

    if missing and not args.allow_missing:
        print(f"ERROR: {len(missing)} venues missing HTML in {PROBE_DIR.relative_to(ROOT)}/:")
        for s in missing:
            print(f"  - {s}.html")
        print("Run scripts/fetch_atlantis_circle.py first, "
              "or pass --allow-missing to emit fallback rows.")
        raise SystemExit(1)

    out_enriched = DATA / "atlantis_circle_enriched.json"
    out_tiers = DATA / "atlantis_circle_tiers.json"
    out_enriched.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    out_tiers.write_text(json.dumps({
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_url": "https://www.atlantis.com/dubai/membership/atlantis-circle",
        "source_note": "Tier % values are hard-coded from migration 0020 — the live membership page is a JS-rendered SPA and the tier table isn't in the HTML.",
        "tiers": TIERS,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {len(rows)} venues -> {out_enriched.relative_to(ROOT)}")
    print(f"  html-jsonld: {sources['html-jsonld']}  fallback-seed: {sources['fallback-seed']}")
    print(f"Wrote tier table -> {out_tiers.relative_to(ROOT)}")
    if missing:
        print(f"WARN: {len(missing)} venues used fallback (HTML missing): {missing}")


if __name__ == "__main__":
    main()
