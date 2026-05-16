"""Filter the raw ADCB offer dump to Dubai-bbox entries.

Reads data/adcb_offers_raw.json (every UAE offer ~3,100), keeps offers
with latitude/longitude inside the Dubai bounding box, and writes
data/adcb_offers_dubai.json.

Mirrors the bbox in filter_fazaa_dubai.py (lat 24.6–25.6, lon 54.5–56.5).

Offers with `latitude=0` and `longitude=0` (online-only / nationwide
services with no fixed address) go to data/adcb_offers_zero_coords.json
for triage — some are legitimate (online retail, telco) and worth
keeping; others are dead entries the user reviews manually.

Offers with no coords AT ALL are also sent to the zero-coords file so
nothing is dropped silently.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SRC = DATA / "adcb_offers_raw.json"
OUT_DUBAI = DATA / "adcb_offers_dubai.json"
OUT_ZERO = DATA / "adcb_offers_zero_coords.json"

# Dubai bounding box — same as filter_fazaa_dubai.py
LAT_MIN, LAT_MAX = 24.6, 25.6
LON_MIN, LON_MAX = 54.5, 56.5


def _coords(row: dict) -> tuple[float | None, float | None]:
    lat = row.get("latitude")
    lng = row.get("longitude")
    try:
        lat_f = float(lat) if lat is not None else None
        lng_f = float(lng) if lng is not None else None
    except (TypeError, ValueError):
        return None, None
    return lat_f, lng_f


def main() -> None:
    rows = json.loads(SRC.read_text(encoding="utf-8"))
    dubai: list[dict] = []
    zero_or_missing: list[dict] = []
    out_of_bbox = 0
    for row in rows:
        lat, lng = _coords(row)
        if lat is None or lng is None or (lat == 0 and lng == 0):
            zero_or_missing.append(row)
            continue
        if LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lng <= LON_MAX:
            dubai.append(row)
        else:
            out_of_bbox += 1

    OUT_DUBAI.write_text(json.dumps(dubai, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT_ZERO.write_text(json.dumps(zero_or_missing, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"input: {len(rows)} offers")
    print(f"  Dubai bbox: {len(dubai)} -> {OUT_DUBAI.relative_to(ROOT)}")
    print(f"  zero/missing coords: {len(zero_or_missing)} -> {OUT_ZERO.relative_to(ROOT)}")
    print(f"  out-of-bbox (other UAE / abroad): {out_of_bbox}")


if __name__ == "__main__":
    main()
