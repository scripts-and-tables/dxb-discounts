"""Filter the raw Fazaa catalog to offers usable in Dubai.

Input has UAE-wide offers (~7,693). Each offer has a `locations[]` array;
typically one entry, but coordinates can be (0, 0) for online/nationwide
services with no fixed address.

Output split:
- entertainer_outlets_dubai.json analogue: offers with at least one location
  in the Dubai bbox.
- a separate triage file for zero-coordinate offers — these are NOT dropped
  silently; the user reviews them to decide which online/nationwide services
  to keep (e.g. delivery, online retail) and which are dead entries.

Bbox: lat 24.6–25.6, lon 54.5–56.5 (covers Dubai metro incl. Hatta, Jebel
Ali, Expo). Same as the Entertainer filter for consistency.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "fazaa_search_raw.json"
DXB = ROOT / "data" / "fazaa_search_dubai.json"
ZERO = ROOT / "data" / "fazaa_search_zero_coords.json"

DXB_LAT_MIN, DXB_LAT_MAX = 24.6, 25.6
DXB_LNG_MIN, DXB_LNG_MAX = 54.5, 56.5


def loc_in_dubai(loc: dict) -> bool:
    lat, lng = loc.get("lat"), loc.get("lon")
    if lat is None or lng is None:
        return False
    if lat == 0 and lng == 0:
        return False
    return DXB_LAT_MIN <= lat <= DXB_LAT_MAX and DXB_LNG_MIN <= lng <= DXB_LNG_MAX


def has_zero_coords_only(offer: dict) -> bool:
    locs = offer.get("locations") or []
    if not locs:
        return True
    return all((l.get("lat") == 0 and l.get("lon") == 0) for l in locs)


def main():
    raw = json.loads(SRC.read_text(encoding="utf-8"))
    print(f"input: {len(raw)} offers")

    dubai: list[dict] = []
    zero: list[dict] = []
    other: list[dict] = []
    for offer in raw:
        locs = offer.get("locations") or []
        if any(loc_in_dubai(l) for l in locs):
            dubai.append(offer)
        elif has_zero_coords_only(offer):
            zero.append(offer)
        else:
            other.append(offer)

    print(f"  Dubai bbox:        {len(dubai)}")
    print(f"  zero-coord triage: {len(zero)}")
    print(f"  other UAE/abroad:  {len(other)}  (dropped)")

    DXB.write_text(json.dumps(dubai, ensure_ascii=False, indent=2), encoding="utf-8")
    ZERO.write_text(json.dumps(zero, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {DXB}")
    print(f"wrote {ZERO}")


if __name__ == "__main__":
    main()
