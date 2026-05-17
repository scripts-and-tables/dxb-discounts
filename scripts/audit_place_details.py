"""Audit description / phone / address gaps across published Places.

Outputs `data/place_details_audit.json` — one row per Place with empty-field
flags. Used by `resolve_place_details.py` as the work-list.

Cheap and read-only: no HTTP, just iterates the DB. The follow-up resolver
step is where the actual enrichment work happens.

Pass --limit N to audit only the first N places (handy for smoke tests).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import django

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "data" / "place_details_audit.json"


def _boot_django() -> None:
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, default=None,
                        help="audit only the first N places")
    args = parser.parse_args()

    _boot_django()
    from apps.places.models import Place  # noqa: E402

    qs = Place.objects.filter(is_published=True).order_by("id")
    if args.limit:
        qs = qs[: args.limit]

    rows: list[dict] = []
    empty_desc = empty_phone = empty_address = empty_website = 0
    for p in qs:
        has_description = bool((p.description or "").strip())
        has_phone = bool((p.phone or "").strip())
        has_address = bool((p.address or "").strip())
        has_website = bool((p.website or "").strip())
        if not has_description: empty_desc += 1
        if not has_phone: empty_phone += 1
        if not has_address: empty_address += 1
        if not has_website: empty_website += 1
        rows.append({
            "id": p.id,
            "slug": p.slug,
            "name": p.name,
            "category": p.category,
            "area": p.area or "",
            "website": p.website or "",
            "lat": float(p.lat) if p.lat is not None else None,
            "lng": float(p.lng) if p.lng is not None else None,
            "has_description": has_description,
            "has_phone": has_phone,
            "has_address": has_address,
            "has_website": has_website,
        })

    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    total = len(rows)
    print(f"audited {total} published Places -> {DEST.relative_to(ROOT)}")
    if total:
        print(f"  empty description: {empty_desc:5d} ({empty_desc/total*100:.1f}%)")
        print(f"  empty phone:       {empty_phone:5d} ({empty_phone/total*100:.1f}%)")
        print(f"  empty address:     {empty_address:5d} ({empty_address/total*100:.1f}%)")
        print(f"  empty website:     {empty_website:5d} ({empty_website/total*100:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
