"""Slim Fazaa + Playbook enriched JSONs to just the fields ingest_offers reads.

Why: Railway's small container OOMs while loading the 35 MB Fazaa JSON
during prod migration. ingest_offers only touches a tiny subset of each
row's fields; the rest (long marketing descriptions, image arrays,
nested unused metadata) is ballast on prod. Slim versions keep the
same paths/field names so ingest_offers works unmodified.

Outputs (overwrites the full files at the same paths):
  data/fazaa_search_enriched.json
  data/playbook_search_enriched.json

Local backups (gitignored under data/_*):
  data/_full_fazaa_search_enriched.json
  data/_full_playbook_search_enriched.json
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


# ---------- Fazaa ----------

def slim_fazaa_row(r: dict) -> dict:
    """Keep only fields read by ingest_offers.ingest_fazaa.

    See apps/discounts/management/commands/ingest_offers.py:213-299.
    """
    det = r.get("detail") or {}
    partner = det.get("partner") or {}
    ld_en = (det.get("localData") or {}).get("en") or {}
    cats = [{"name": c.get("name", "")} for c in (det.get("categories") or []) if isinstance(c, dict)]
    locs = r.get("locations") or []
    # Only first location's coords are used; keep it as a single-element list
    # so the existing `locs[0]` access continues to work.
    if locs and isinstance(locs[0], dict):
        first = {"lat": locs[0].get("lat"), "lon": locs[0].get("lon")}
        slim_locs = [first]
    else:
        slim_locs = []
    return {
        "slug": r.get("slug"),
        "partnerName": r.get("partnerName"),
        "title": r.get("title"),
        "subTitle": r.get("subTitle"),
        "locations": slim_locs,
        "detail": {
            "partner": {
                "partnerName": partner.get("partnerName"),
                "partnerLink": partner.get("partnerLink"),
            },
            "categories": cats,
            "discount": det.get("discount"),
            "discountType": det.get("discountType"),
            "offerExpiry": det.get("offerExpiry"),
            "localData": {"en": {
                "title": ld_en.get("title"),
                "shortDescription": ld_en.get("shortDescription"),
                "description": ld_en.get("description"),
            }},
        },
    }


# ---------- Playbook ----------

def slim_playbook_row(r: dict) -> dict:
    """Keep only fields read by ingest_offers.ingest_playbook.

    See apps/discounts/management/commands/ingest_offers.py:308-373.
    """
    det = r.get("detail") or {}
    slim_highlights = [
        {
            "Id": h.get("Id"),
            "Name": h.get("Name"),
            "GeneralDescription": h.get("GeneralDescription"),
            "DetailedDescription": h.get("DetailedDescription"),
        }
        for h in (det.get("Highlights") or [])
        if isinstance(h, dict)
    ]
    return {
        "Id": r.get("Id"),
        "Name": r.get("Name"),
        "Lat": r.get("Lat"),
        "Lng": r.get("Lng"),
        "AreaName": r.get("AreaName"),
        "BuildingName": r.get("BuildingName"),
        "detail": {
            # StatusCode is the only "is this row valid?" gate ingest checks.
            "StatusCode": det.get("StatusCode"),
            "Phone": det.get("Phone"),
            "WebsiteUrl": det.get("WebsiteUrl"),
            "About": det.get("About"),
            "Highlights": slim_highlights,
        },
    }


# ---------- driver ----------

def slim_file(src: Path, slimmer) -> tuple[int, int]:
    """Slim `src` in place. Returns (orig_size, new_size) in bytes."""
    backup = src.parent / f"_full_{src.name}"
    if not backup.exists():
        shutil.copy2(src, backup)
    orig_size = src.stat().st_size
    rows = json.loads(src.read_text(encoding="utf-8"))
    slim = [slimmer(r) for r in rows]
    src.write_text(json.dumps(slim, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return orig_size, src.stat().st_size


def main() -> int:
    targets = [
        (DATA / "fazaa_search_enriched.json", slim_fazaa_row),
        (DATA / "playbook_search_enriched.json", slim_playbook_row),
    ]
    for src, slimmer in targets:
        if not src.exists():
            print(f"skipping {src.name}: not present")
            continue
        orig, new = slim_file(src, slimmer)
        ratio = (new / orig) * 100 if orig else 0
        print(f"{src.name}: {orig // 1024} KB -> {new // 1024} KB ({ratio:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
