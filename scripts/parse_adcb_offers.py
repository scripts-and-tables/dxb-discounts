"""Normalize the Dubai-filtered ADCB offers into the enriched JSON
that `ingest_offers --source adcb_touchpoints` consumes.

Reads data/adcb_offers_dubai.json, regexes the discount % / fixed-AED
out of `offerName` (the API stores it as freeform English in the
title, e.g. "10% discount on best available rate at..."), normalizes
fields, and writes data/adcb_offers_enriched.json.

The discount-type classification is best-effort: well-formed offers
get PERCENTAGE / FIXED_PRICE / BOGO; anything we can't pattern-match
falls through to OTHER with the original text preserved in description
(don't drop data — let the ingest model it as "Special offer" with
the brand and the raw title).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "adcb_offers_dubai.json"
OUT = ROOT / "data" / "adcb_offers_enriched.json"

# Discount-extraction patterns (run in order; first hit wins).
PCT_PATTERNS = [
    # "Up to 50% off"  /  "Up to 50% discount"
    re.compile(r"\bup\s*to\s+(\d{1,2})\s*%\s*(?:off|discount)\b", re.IGNORECASE),
    # "Get 20% off" / "20% discount on" / "20% off your" / "Save 20%"
    re.compile(r"\b(?:get|save|enjoy)?\s*(\d{1,2})\s*%\s*(?:off|discount|savings?)\b", re.IGNORECASE),
    # generic "<n>%"
    re.compile(r"\b(\d{1,2})\s*%\b", re.IGNORECASE),
]
AED_OFF_PATTERNS = [
    # "AED 100 off" / "AED 50 cashback"
    re.compile(r"\bAED\s+(\d{1,5}(?:\.\d{1,2})?)\s+(?:off|cashback|discount|savings?)\b", re.IGNORECASE),
    # "Flat AED 50 off"
    re.compile(r"\bflat\s+AED\s+(\d{1,5}(?:\.\d{1,2})?)\b", re.IGNORECASE),
]
BOGO_PATTERN = re.compile(
    r"\b(buy\s*(?:1|one)\s*get\s*(?:1|one)\b.{0,40}\b(?:free|complimentary)|"
    r"buy\s*(?:2|two|3|three)\s*get\s*(?:1|one)\b.{0,30}\bfree|"
    r"2\s*[\-\s]*for\s*[\-\s]*1|two\s*for\s*one|bogo)\b",
    re.IGNORECASE,
)

# Words that suggest the offer isn't a structured discount and shouldn't
# be force-mapped to a percentage. If the title says "complimentary" /
# "free" but isn't a BOGO, leave as OTHER so the user-facing label is
# accurate.
LIKELY_NON_PERCENTAGE = re.compile(
    r"\b(complimentary|free\s+(?:upgrade|gift|night|breakfast)|gift|voucher)\b",
    re.IGNORECASE,
)


def _en(field) -> str:
    """Get the English value from a [{language, value}] list. Empty if missing."""
    if not isinstance(field, list):
        return field or "" if isinstance(field, str) else ""
    for entry in field:
        if isinstance(entry, dict) and entry.get("language") in ("en-US", "en"):
            return (entry.get("value") or "").strip()
    return ""


def _classify(title: str) -> tuple[str, dict]:
    """Return (discount_type, parsed-fields-dict). discount_type ∈ {
    'percentage', 'fixed_price', 'bogo', 'other'
    }."""
    if not title:
        return "other", {}

    # BOGO patterns first — they're unambiguous and shouldn't be misread
    # as percentage if "buy 2 get 1" stays in the title.
    if BOGO_PATTERN.search(title):
        return "bogo", {}

    # AED <X> off
    for p in AED_OFF_PATTERNS:
        m = p.search(title)
        if m:
            try:
                return "fixed_price", {"fixed_price_aed": float(m.group(1))}
            except ValueError:
                pass

    # Percentage — but skip if the title also looks like a "complimentary
    # gift" type that just happens to mention a %.
    for p in PCT_PATTERNS:
        m = p.search(title)
        if m:
            pct = int(m.group(1))
            if 1 <= pct <= 99:
                # Don't tag as percentage if the title is dominated by
                # gift/voucher/complimentary language without a real
                # "% off" anchor — but if we matched "X% off" or
                # "X% discount" the anchor IS there.
                if LIKELY_NON_PERCENTAGE.search(title) and not re.search(
                    r"\d+\s*%\s*(off|discount)", title, re.IGNORECASE
                ):
                    break
                return "percentage", {"percentage": pct}

    return "other", {}


def parse_offer(row: dict) -> dict:
    offer_name = _en(row.get("offerName"))
    description_en = _en(row.get("offerDescription"))
    # offerDescription is HTML wrapped in <p>…</p> — strip the wrapper.
    description_clean = re.sub(r"<[^>]+>", "", description_en).strip()

    brand_name = _en(row.get("brandName")) or _en(row.get("merchantName"))
    merchant_name = _en(row.get("merchantName")) or brand_name
    category = _en(row.get("category", {}).get("name") if isinstance(row.get("category"), dict) else None)

    discount_type, parsed = _classify(offer_name)
    return {
        "id": row.get("id"),
        "type": row.get("type"),                 # API's type: Discount / Fixed-value / etc.
        "discount_type": discount_type,          # our model's discount_type
        "title": offer_name[:200],
        "brand_name": brand_name,
        "merchant_name": merchant_name,
        "category": category,
        "description": description_clean,
        "raw_offer_name": offer_name,
        "brand_logo": (row.get("brandLogo") or "").strip(),
        "merchant_logo": (row.get("merchantLogo") or "").strip(),
        "offer_image": (row.get("offerImage") or "").strip(),
        "lat": row.get("latitude"),
        "lng": row.get("longitude"),
        "end_time": row.get("endTime"),
        **parsed,
    }


def main() -> None:
    rows = json.loads(SRC.read_text(encoding="utf-8"))
    out = [parse_offer(r) for r in rows]
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    # Classification report
    counts = {"percentage": 0, "fixed_price": 0, "bogo": 0, "other": 0}
    for o in out:
        counts[o["discount_type"]] += 1
    print(f"Parsed {len(out)} offers -> {OUT.relative_to(ROOT)}")
    for k, v in counts.items():
        pct = (v / len(out) * 100) if out else 0
        print(f"  {k:12s}: {v:5d} ({pct:5.1f}%)")


if __name__ == "__main__":
    main()
