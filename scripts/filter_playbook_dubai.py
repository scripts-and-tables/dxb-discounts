"""Filter the raw Playbook catalog to Dubai venues.

Input has UAE-wide venues. Each venue has both `StateName` (string) and
`Lat`/`Lng`. We trust StateName as the primary signal (Playbook's editorial
team curates it) and use the Dubai bbox as a secondary check to flag any
mislabeled rows. Same bbox as filter_fazaa_dubai.py / filter_entertainer_dubai.py
for cross-source consistency.

Output split:
- playbook_search_dubai.json — venues with StateName=='Dubai' AND coords in
  the Dubai bbox.
- playbook_search_zero_coords.json — venues with lat=lng=0 (no fixed
  address). Reviewed manually before deciding what to do.
- (everything else dropped silently — Abu Dhabi etc.)

Bbox: lat 24.6–25.6, lon 54.5–56.5 (covers Dubai metro incl. Hatta, Jebel
Ali, Expo). Same as the other source filters.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "playbook_search_raw.json"
DXB = ROOT / "data" / "playbook_search_dubai.json"
ZERO = ROOT / "data" / "playbook_search_zero_coords.json"

DXB_LAT_MIN, DXB_LAT_MAX = 24.6, 25.6
DXB_LNG_MIN, DXB_LNG_MAX = 54.5, 56.5


def in_dubai_bbox(lat, lng) -> bool:
    if lat is None or lng is None:
        return False
    if lat == 0 and lng == 0:
        return False
    return DXB_LAT_MIN <= lat <= DXB_LAT_MAX and DXB_LNG_MIN <= lng <= DXB_LNG_MAX


def main():
    raw = json.loads(SRC.read_text(encoding="utf-8"))
    print(f"input: {len(raw)} venues")

    dubai: list[dict] = []
    zero: list[dict] = []
    state_mismatch: list[dict] = []
    other: list[dict] = []
    for v in raw:
        state = v.get("StateName", "")
        lat, lng = v.get("Lat"), v.get("Lng")
        if lat == 0 and lng == 0:
            zero.append(v)
            continue
        if state == "Dubai" and in_dubai_bbox(lat, lng):
            dubai.append(v)
        elif state == "Dubai" or in_dubai_bbox(lat, lng):
            # StateName says Dubai but bbox disagrees, or vice versa.
            # Worth surfacing — usually a bad coordinate or a Dubai venue with a
            # typo in StateName. We keep the StateName signal (curator-set) and
            # accept if EITHER signal points to Dubai.
            state_mismatch.append(v)
            if state == "Dubai":
                dubai.append(v)
        else:
            other.append(v)

    print(f"  Dubai (state + bbox match): {len(dubai)}")
    print(f"  state/bbox mismatch:        {len(state_mismatch)}  (kept if StateName=='Dubai')")
    print(f"  zero-coord triage:          {len(zero)}")
    print(f"  other emirates (dropped):   {len(other)}")

    DXB.write_text(json.dumps(dubai, ensure_ascii=False, indent=2), encoding="utf-8")
    ZERO.write_text(json.dumps(zero, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {DXB}")
    print(f"wrote {ZERO}")


if __name__ == "__main__":
    main()
