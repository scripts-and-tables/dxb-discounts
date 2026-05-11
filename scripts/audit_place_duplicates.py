"""Find cross-source duplicate Place rows and write a reviewable JSON.

Buckets every published Place by the canonical normalize_name from
apps.places.matching, then for each bucket with 2+ Places enumerates
pairs and scores them on three signals:

  1. coord proximity (haversine < 150m)
  2. same website domain (Place.logo_domain match)
  3. address-token overlap (>= 2 shared tokens >= 3 chars)

A cluster is `kind = "cross_source"` if its Places have complementary
source_program sets — i.e. one Place has at least one source the other
lacks. That's the strongest "split across ingests" signal.

Clusters of 2 Places that are cross_source AND have at least one
corroborating signal land in confidence=high with auto_merge=true.
Everything else is medium/low and review-only.

Output: data/place_duplicates_enriched.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import django

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "data" / "place_duplicates_enriched.json"


def _boot_django() -> None:
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()


def _address_tokens(addr: str) -> set[str]:
    """Return tokens >=3 chars, lowercased, alpha-only — for overlap scoring."""
    if not addr:
        return set()
    out: set[str] = set()
    for tok in addr.lower().split():
        tok = "".join(c for c in tok if c.isalnum())
        if len(tok) >= 3:
            out.add(tok)
    return out


def _has_real_coords(p) -> bool:
    """True iff this Place has lat/lng AND they aren't the (0, 0) null-island
    sentinel some ingest paths leave behind."""
    if p.lat is None or p.lng is None:
        return False
    return not (float(p.lat) == 0.0 and float(p.lng) == 0.0)


def _score_pair(a, b, haversine, logo_domain) -> dict:
    """Return the match_signals dict for a candidate pair (a, b)."""
    coord_proximity_m = None
    if _has_real_coords(a) and _has_real_coords(b):
        coord_proximity_m = haversine(float(a.lat), float(a.lng), float(b.lat), float(b.lng))

    same_domain = False
    if a.website and b.website:
        da = logo_domain(a)
        db = logo_domain(b)
        same_domain = bool(da) and da == db

    a_tokens = _address_tokens(a.address)
    b_tokens = _address_tokens(b.address)
    addr_overlap = len(a_tokens & b_tokens)

    a_src = a._source_programs
    b_src = b._source_programs
    complementary = bool((a_src - b_src) or (b_src - a_src)) and bool(a_src) and bool(b_src)

    return {
        "normalized_name_match": True,
        "coord_proximity_m": round(coord_proximity_m, 1) if coord_proximity_m is not None else None,
        "same_website_domain": same_domain,
        "address_overlap_tokens": addr_overlap,
        "complementary_sources": complementary,
    }


def _confidence_of(signals: dict, areas_match: bool, key_len: int) -> tuple[str, bool]:
    """Return (confidence_label, auto_merge_eligible).

    Anti-signal: two Places with real coords > 500m apart are almost
    certainly distinct branches of a chain, NEVER the same business —
    auto-merging them would silently destroy data. Downgrade to medium.
    """
    proximity = signals["coord_proximity_m"]
    if proximity is not None and proximity > 500:
        if signals["complementary_sources"]:
            return "medium", False  # likely branches of same chain
        return "low", False

    has_strong = (
        (proximity is not None and proximity < 150)
        or signals["same_website_domain"]
        or signals["address_overlap_tokens"] >= 2
    )

    # Very short normalized keys (< 4 chars) only survived because stopword
    # stripping ate the rest. Real brand names are at least 4 chars; anything
    # shorter is a single common word that may match unrelated venues sharing
    # a building (e.g. "The H Dubai" hotel vs "H Bar" bar inside it).
    if key_len < 4:
        return "medium", False

    if signals["complementary_sources"] and has_strong:
        return "high", True
    if signals["complementary_sources"]:
        return "medium", False
    if has_strong:
        return "medium", False
    if areas_match:
        return "medium", False
    return "low", False


def _suggest_canonical(places) -> int:
    """Tie-break: most discounts -> has coords -> has address -> has logo override -> oldest id."""
    def key(p):
        return (
            -p._discount_count,
            0 if p.lat is not None and p.lng is not None else 1,
            0 if p.address else 1,
            0 if p.logo_url_override else 1,
            p.id,
        )
    return min(places, key=key).id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--include-low", action="store_true",
                        help="include low-confidence (branches-only) clusters in the output")
    args = parser.parse_args()

    _boot_django()
    from apps.places.models import Place  # noqa: E402
    from apps.places.matching import normalize_name, _haversine_m  # noqa: E402
    from apps.discounts.models import Discount  # noqa: E402

    places = list(Place.objects.filter(is_published=True))
    print(f"loaded {len(places)} published Places")

    # Attach source_programs + discount_count to each Place in one query.
    source_map: dict[int, set[str]] = defaultdict(set)
    count_map: dict[int, int] = defaultdict(int)
    for pid, src, active in Discount.objects.values_list("place_id", "source_program", "is_active"):
        if not src:
            continue
        source_map[pid].add(src)
        if active:
            count_map[pid] += 1
    for p in places:
        p._source_programs = source_map.get(p.id, set())
        p._discount_count = count_map.get(p.id, 0)

    # Bucket by normalized name.
    buckets: dict[str, list] = defaultdict(list)
    for p in places:
        key = normalize_name(p.name)
        if not key:
            continue
        buckets[key].append(p)

    clusters: list[dict] = []
    for key, members in buckets.items():
        if len(members) < 2:
            continue

        # Sort deterministically so canonical-suggestion is stable across runs.
        members.sort(key=lambda p: p.id)

        # We only score pairs. For clusters with 3+ Places, emit the first
        # pair fully scored, but mark needs_human_review so the user inspects.
        a, b = members[0], members[1]
        signals = _score_pair(a, b, _haversine_m, lambda p: p.logo_domain)
        areas_match = bool(a.area) and a.area.strip().lower() == (b.area or "").strip().lower()
        confidence, auto_merge = _confidence_of(signals, areas_match, len(key))

        # Force-downgrade clusters of >2 Places to review-only (genuine cross-
        # source duplicates almost always come in pairs, not triples).
        needs_review_note = ""
        if len(members) > 2:
            auto_merge = False
            confidence = "medium" if confidence == "high" else confidence
            needs_review_note = f"cluster has {len(members)} places; auto-merge disabled"

        # Determine kind for downstream readers.
        if signals["complementary_sources"]:
            kind = "cross_source"
        else:
            kind = "likely_branches"  # same source(s), probably real distinct branches

        cluster = {
            "cluster_id": key,
            "kind": kind,
            "places": [
                {
                    "id": p.id, "slug": p.slug, "name": p.name,
                    "discount_count": p._discount_count,
                    "source_programs": sorted(p._source_programs),
                    "lat": float(p.lat) if p.lat is not None else None,
                    "lng": float(p.lng) if p.lng is not None else None,
                    "area": p.area, "address": p.address, "website": p.website,
                    "logo_url_override": p.logo_url_override,
                }
                for p in members
            ],
            "match_signals": signals,
            "confidence": confidence,
            "auto_merge": auto_merge,
            "suggested_canonical_id": _suggest_canonical(members),
            "notes": needs_review_note,
        }
        if confidence == "low" and not args.include_low:
            continue
        if kind == "likely_branches" and confidence != "high":
            # Don't drown the output in chain-branch buckets; they're not duplicates.
            continue
        clusters.append(cluster)

    # Sort: high+auto first, then medium, then likely_branches; within each
    # bucket order by cluster_id for determinism.
    def sort_key(c):
        return (
            0 if c["auto_merge"] else (1 if c["confidence"] == "medium" else 2),
            c["cluster_id"],
        )
    clusters.sort(key=sort_key)

    DEST.write_text(json.dumps(clusters, ensure_ascii=False, indent=2), encoding="utf-8")

    by_conf: dict[str, int] = defaultdict(int)
    by_kind: dict[str, int] = defaultdict(int)
    auto = 0
    for c in clusters:
        by_conf[c["confidence"]] += 1
        by_kind[c["kind"]] += 1
        if c["auto_merge"]:
            auto += 1
    print(f"\nwrote {DEST}")
    print(f"  clusters total: {len(clusters)}")
    for k in ("high", "medium", "low"):
        print(f"  confidence={k}: {by_conf.get(k, 0)}")
    for k in ("cross_source", "likely_branches"):
        print(f"  kind={k}: {by_kind.get(k, 0)}")
    print(f"  auto-merge eligible: {auto}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
