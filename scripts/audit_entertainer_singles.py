"""Audit Places that hold exactly one Entertainer Discount each.

For every Place whose new-style entertainer discount count is 1, parse the
merchant/outlet id from the Discount slug, look up the corresponding outlet
in data/entertainer_outlets_enriched.json, and report any case where the
source has multiple offers but the DB only has one — that's a silent
ingest drop we'd want to investigate.

Read-only. Prints a summary and exits 0.

Usage:
  python scripts/audit_entertainer_singles.py
  python scripts/audit_entertainer_singles.py --limit 50
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.db.models import Count, Q  # noqa: E402

from apps.discounts.models import Discount  # noqa: E402
from apps.places.models import Place  # noqa: E402


SRC = ROOT / "data" / "entertainer_outlets_enriched.json"


def index_source() -> dict[tuple[int, int], dict]:
    """Map (merchant_id, outlet_id) → outlet dict from the enriched JSON."""
    if not SRC.exists():
        print(f"missing {SRC} — run refresh-entertainer first", file=sys.stderr)
        sys.exit(1)
    rows = json.loads(SRC.read_text(encoding="utf-8"))
    idx: dict[tuple[int, int], dict] = {}
    for row in rows:
        m = row.get("merchant_id")
        o = row.get("outlet_id")
        if m and o:
            idx[(int(m), int(o))] = row
    return idx


def count_source_offers(outlet: dict) -> int:
    """Count distinct offer_ids in the outlet's offer_sections."""
    seen: set = set()
    for section in outlet.get("offer_sections") or []:
        for offer in section.get("offers") or []:
            oid = offer.get("offer_id")
            if oid:
                seen.add(oid)
    return len(seen)


def parse_slug(slug: str) -> tuple[int, int, int] | None:
    """Pull (merchant_id, outlet_id, offer_id) out of an entertainer-* slug."""
    if not slug.startswith("entertainer-"):
        return None
    parts = slug.split("-")
    if len(parts) < 4:
        return None
    try:
        return int(parts[1]), int(parts[2]), int(parts[3])
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0, help="Audit only the first N affected Places.")
    args = ap.parse_args()

    src_index = index_source()
    print(f"loaded {len(src_index)} outlets from enriched JSON")

    ent_q = Q(discounts__source_program="entertainer")
    new_q = Q(discounts__slug__startswith="entertainer-")
    singles = (
        Place.objects.filter(ent_q)
        .annotate(n=Count("discounts", filter=ent_q))
        .filter(n=1)
    )
    # Only audit places whose single discount is the NEW format (legacy ent-* is a separate problem).
    singles = singles.filter(new_q).distinct()

    total = singles.count()
    print(f"places with exactly 1 entertainer-* discount: {total}")

    if args.limit:
        singles = singles[: args.limit]

    correct = 0
    not_in_source = 0
    mismatches: list[tuple[str, int, int]] = []  # (place_slug, db_count, src_count)
    for place in singles.iterator():
        d = place.discounts.filter(slug__startswith="entertainer-").first()
        parsed = parse_slug(d.slug) if d else None
        if not parsed:
            continue
        m, o, _ = parsed
        outlet = src_index.get((m, o))
        if not outlet:
            not_in_source += 1
            continue
        src_count = count_source_offers(outlet)
        if src_count <= 1:
            correct += 1
        else:
            mismatches.append((place.slug, 1, src_count))

    print()
    print("--- Audit Result ---")
    print(f"  correct (source has 1 offer):        {correct}")
    print(f"  outlet missing from enriched JSON:   {not_in_source}")
    print(f"  MISMATCH (source > DB):              {len(mismatches)}")
    if mismatches:
        print()
        print("first 30 mismatches (place_slug, db_count, src_count):")
        for s, db_n, src_n in mismatches[:30]:
            print(f"  /places/{s}/  db={db_n}  src={src_n}")
        # Distribution of src counts among mismatches
        from collections import Counter
        dist = Counter(src_n for _, _, src_n in mismatches)
        print()
        print(f"src-count distribution among mismatches: {dict(sorted(dist.items()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
