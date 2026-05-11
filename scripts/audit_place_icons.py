"""Audit icon availability across all published Places.

Outputs `data/place_icons_audit.json` — a flat inventory of every Place
plus a `has_website` flag. The resolver step reads this file to drive its
cascade.

Why so simple? `logo.clearbit.com` was deprecated by HubSpot in late
2023 (DNS no longer resolves), so the previous "HEAD-check the Clearbit
URL" plan is moot — *every* Place currently falls back to a 32px Google
favicon. The two interesting buckets that remain are:
  - Places with no website at all (no icon possible).
  - Places with a website (favicon fallback only — could be upgraded).

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
DEST = ROOT / "data" / "place_icons_audit.json"


def _boot_django() -> None:
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, default=None, help="audit only the first N places")
    args = parser.parse_args()

    _boot_django()
    from apps.places.models import Place  # noqa: E402

    qs = Place.objects.filter(is_published=True).order_by("id")
    if args.limit:
        qs = qs[: args.limit]

    rows: list[dict] = []
    for p in qs:
        rows.append({
            "id": p.id,
            "slug": p.slug,
            "name": p.name,
            "category": p.category,
            "area": p.area,
            "website": p.website,
            "logo_domain": p.logo_domain,
            "has_website": bool(p.website),
        })

    DEST.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    total = len(rows)
    with_site = sum(1 for r in rows if r["has_website"])
    no_site = total - with_site
    by_cat: dict[str, tuple[int, int]] = {}
    for r in rows:
        t, n = by_cat.get(r["category"], (0, 0))
        by_cat[r["category"]] = (t + 1, n + (0 if r["has_website"] else 1))

    print(f"wrote {DEST}")
    print(f"  total places: {total}")
    print(f"  with website: {with_site} ({with_site * 100 // total if total else 0}%)")
    print(f"  no website:   {no_site} ({no_site * 100 // total if total else 0}%)")
    print("  by category (total / no-website):")
    for cat, (t, n) in sorted(by_cat.items(), key=lambda kv: -kv[1][0]):
        print(f"    {cat:<12} {t:>5} / {n:>5} ({n * 100 // t if t else 0}% missing)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
