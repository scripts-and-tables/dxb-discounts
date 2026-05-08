"""Filter the raw Entertainer outlet list down to outlets actually in Dubai.

The Entertainer's `country=AE / location_id=1` query is loose — it returns
UAE outlets plus cross-border ones (Saudi, Qatar, Kuwait, Bahrain, Oman) that
a Dubai subscriber can also redeem. This script applies two cuts:

1. Coordinate bounding box (Dubai metro area incl. Hatta + expo + Jebel Ali).
2. Outlet-name exclusion list for venues whose coordinates land just inside the
   Dubai bbox but that are explicitly named for another emirate (Sharjah,
   Ajman, RAK, UAQ, Fujairah, Al Ain, Abu Dhabi) or a Saudi city.

Output: data/entertainer_outlets_dubai.json — same shape as the input, just
filtered.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "entertainer_outlets_raw.json"
DEST = ROOT / "data" / "entertainer_outlets_dubai.json"

# Loose Dubai bbox — covers central Dubai, JBR/Marina, Palm, Hatta, Expo,
# Jebel Ali, DXB airport, Dubai-side of Sharjah/Ajman edges.
DXB_LAT_MIN, DXB_LAT_MAX = 24.6, 25.6
DXB_LNG_MIN, DXB_LNG_MAX = 54.5, 56.5

# Outlets whose coords land inside the bbox but that are explicitly named
# for somewhere else. Match on outlet_name AND merchant_name (some merchants
# include the emirate in the merchant_name, e.g. "ChicKing - Abu Dhabi").
NON_DUBAI_NAME_PATTERNS = [
    r"\bsharjah\b",
    r"\bajman\b",
    r"\babu\s*dhabi\b",
    r"\bras\s*al\s*khaimah\b",
    r"\brak\b",
    r"\bumm\s*al\s*quwain\b",
    r"\buaq\b",
    r"\bfujairah\b",
    r"\bal\s*ain\b",
    r"\bdammam\b",
    r"\briyadh\b",
    r"\bjeddah\b",
    r"\bdoha\b",
    r"\bkuwait\b",
    r"\bbahrain\b",
    r"\boman\b",
    r"\bmuscat\b",
]
NON_DUBAI_RE = re.compile("|".join(NON_DUBAI_NAME_PATTERNS), re.IGNORECASE)


def is_in_dubai_bbox(outlet: dict) -> bool:
    coords = outlet.get("outlet_coordinates") or {}
    lat = coords.get("lat")
    lng = coords.get("lon")
    if lat is None or lng is None or lat == 0 or lng == 0:
        return False
    return DXB_LAT_MIN <= lat <= DXB_LAT_MAX and DXB_LNG_MIN <= lng <= DXB_LNG_MAX


def name_says_non_dubai(outlet: dict) -> bool:
    haystack = f"{outlet.get('outlet_name', '')} | {outlet.get('merchant_name', '')}"
    return bool(NON_DUBAI_RE.search(haystack))


def main():
    raw = json.loads(SRC.read_text(encoding="utf-8"))
    print(f"input: {len(raw)} outlets")

    bbox_keep = [o for o in raw if is_in_dubai_bbox(o)]
    print(f"  after bbox cut: {len(bbox_keep)} (-{len(raw) - len(bbox_keep)})")

    final = [o for o in bbox_keep if not name_says_non_dubai(o)]
    print(f"  after name cut: {len(final)} (-{len(bbox_keep) - len(final)})")

    merchants = {o["merchant_id"] for o in final}
    print(f"  unique merchants in Dubai: {len(merchants)}")

    DEST.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {DEST}")


if __name__ == "__main__":
    main()
