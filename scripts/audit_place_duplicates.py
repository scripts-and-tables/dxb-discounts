"""Find duplicate Place rows across three patterns:

1. `cross_source` — two Places with the same normalized name and
   complementary source programs (e.g. "Kanpai" + "Kanpai Dubai").

2. `brand_with_branches` — a brand-level Place (1-3 normalized tokens)
   plus 2+ "branches" whose normalized name starts with the brand's
   normalized name + a location suffix (e.g. "360 Play" + "360 Play
   Al Ghurair Centre", "360 Play Reef Mall", ...).

3. `synthesizable_branches` — 2+ Places sharing a common 2-3 token
   prefix but no Place exists at that prefix alone (e.g. "ACAI Luv
   Al Barsha" + "ACAI Luv Aswaaq Mall" with no plain "ACAI Luv" entry).

Auto-merge is enabled only on high-precision rules; everything else
lands in the JSON for human review.

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


def audit(include_low: bool = False) -> int:
    """In-process audit. Django must already be set up (used from migrations).
    Writes data/place_duplicates_enriched.json. Returns cluster count."""
    from apps.places.models import Place
    from apps.places.matching import normalize_name, _haversine_m
    from apps.discounts.models import Discount

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

    # Attribute each multi-token Place to its longest brand prefix (up to 3
    # tokens), where a "brand prefix" is a normalized name held by some OTHER
    # Place. Excluding-self lets the Place "Krispy Kreme - Mall" (norm
    # "krispy kreme mall") become a branch of "Krispy Kreme" (norm "krispy
    # kreme") even though its own norm is 3 tokens.
    branches_by_brand: dict[str, list] = defaultdict(list)
    unattributed: list = []
    for p in places:
        n = normalize_name(p.name)
        if not n:
            continue
        tokens = n.split()
        if len(tokens) < 2:
            continue
        found_brand: str | None = None
        for k in range(min(len(tokens) - 1, 3), 0, -1):
            prefix = " ".join(tokens[:k])
            if any(pp.id != p.id for pp in buckets.get(prefix, [])):
                found_brand = prefix
                break
        if found_brand is not None:
            branches_by_brand[found_brand].append(p)
        else:
            unattributed.append(p)

    # Refinement pass: if all attributed branches under a brand B actually
    # share a LONGER common prefix L (LCP > B), the real brand is L not B.
    # Catches cases like the one-token Place "Papa Dubai" (norm "papa")
    # spuriously claiming all "Papa Johns Pizza ..." branches.
    refined_branches_by_brand: dict[str, list] = defaultdict(list)
    refined_synth: dict[str, list] = defaultdict(list)
    for brand, branches in branches_by_brand.items():
        if len(branches) < 2:
            refined_branches_by_brand[brand].extend(branches)
            continue
        token_lists = [normalize_name(b.name).split() for b in branches]
        lcp_k = 0
        for i in range(min(len(tl) for tl in token_lists)):
            if all(tl[i] == token_lists[0][i] for tl in token_lists):
                lcp_k = i + 1
            else:
                break
        lcp = " ".join(token_lists[0][:lcp_k])
        brand_tokens = brand.split()
        if lcp_k > len(brand_tokens):
            # Branches share a longer prefix than the attributed brand.
            if lcp in buckets and buckets[lcp]:
                # A Place exists at the longer prefix — promote to brand_with_branches there.
                refined_branches_by_brand[lcp].extend(branches)
            else:
                # No Place at the longer prefix — synthesizable.
                refined_synth[lcp].extend(branches)
        else:
            refined_branches_by_brand[brand].extend(branches)
    branches_by_brand = refined_branches_by_brand

    # Norms claimed by brand_with_branches — skip them in the cross_source
    # loop so they don't double-emit.
    claimed_norms: set[str] = set()

    clusters: list[dict] = []

    # ---- Pass 1: brand_with_branches ----
    for prefix, branches in sorted(branches_by_brand.items()):
        if len(branches) < 2:
            continue
        brand_places = sorted(buckets[prefix], key=lambda p: p.id)
        # Source-set summaries for the cluster decision.
        brand_src: set[str] = set()
        for bp in brand_places:
            brand_src |= bp._source_programs
        branch_src: set[str] = set()
        for br in branches:
            branch_src |= br._source_programs

        # Auto-merge rules: exactly one brand row AND branches are 100%
        # Entertainer. The brand row's sources don't matter — Entertainer
        # branches always collapse safely into a single canonical (per-outlet
        # ingest noise is the cause).
        single_brand = len(brand_places) == 1
        branches_entertainer_only = bool(branch_src) and branch_src.issubset({"entertainer"})

        if single_brand and branches_entertainer_only:
            confidence, auto_merge = "high", True
        else:
            confidence, auto_merge = "medium", False

        canonical_id = brand_places[0].id if single_brand else _suggest_canonical(brand_places)

        cluster = {
            "cluster_id": prefix,
            "kind": "brand_with_branches",
            "brand_id": canonical_id if single_brand else None,
            "branch_ids": [b.id for b in sorted(branches, key=lambda p: p.id)],
            "brand_source_programs": sorted(brand_src),
            "branch_source_programs": sorted(branch_src),
            "places": [
                {
                    "id": p.id, "slug": p.slug, "name": p.name,
                    "discount_count": p._discount_count,
                    "source_programs": sorted(p._source_programs),
                    "lat": float(p.lat) if p.lat is not None else None,
                    "lng": float(p.lng) if p.lng is not None else None,
                    "area": p.area, "address": p.address, "website": p.website,
                    "logo_url_override": p.logo_url_override,
                    "is_brand": p in brand_places,
                }
                for p in (brand_places + sorted(branches, key=lambda p: p.id))
            ],
            "confidence": confidence,
            "auto_merge": auto_merge,
            "suggested_canonical_id": canonical_id,
            "notes": "" if single_brand else f"{len(brand_places)} brand-level entries; review canonical pick",
        }
        clusters.append(cluster)
        claimed_norms.add(prefix)
        for br in branches:
            claimed_norms.add(normalize_name(br.name))

    # ---- Pass 2: synthesizable_branches ----
    # Group unattributed multi-token Places by their first 2 tokens, then
    # within each group extend to the longest common token-prefix shared by
    # all members. This handles brands like "All You Can Keto" (4 tokens)
    # whose branches would otherwise bucket under just "all you".
    initial_groups: dict[str, list] = defaultdict(list)
    for p in unattributed:
        tokens = normalize_name(p.name).split()
        if len(tokens) < 2:
            continue  # 1-token Places are their own brand, not branches
        # Bucket by FIRST token. This is wider than first-2 so that
        # "Pastaria - Al Barsha" and "Pastaria - International City"
        # converge to one cluster (LCP "pastaria") instead of splitting
        # into "pastaria al" / "pastaria international" sub-buckets.
        first = tokens[0]
        if first in buckets:
            # Some Place has exactly this 1-token norm — would have been
            # claimed in pass 1; skip.
            continue
        initial_groups[first].append(p)

    syn_groups: dict[str, list] = defaultdict(list)
    for prefix2, members in initial_groups.items():
        if len(members) < 2:
            continue
        token_lists = [normalize_name(p.name).split() for p in members]
        # Find LCP: max k such that all members agree on first k tokens AND
        # each member has at least k+1 tokens (so a suffix exists).
        max_k = min(len(tl) - 1 for tl in token_lists)
        lcp_k = 0
        for k in range(1, max_k + 1):
            if all(tl[k - 1] == token_lists[0][k - 1] for tl in token_lists):
                lcp_k = k
            else:
                break
        if lcp_k == 0:
            continue
        # Require either:
        #   - 2+ LCP tokens (specific brand like "All You Can Keto"), OR
        #   - 1 LCP token that's distinctive (>=6 chars) AND 3+ members.
        # 1-token + 2 members is too risky (might be coincidental).
        if lcp_k == 1:
            if len(token_lists[0][0]) < 6 or len(members) < 3:
                continue
        lcp = " ".join(token_lists[0][:lcp_k])
        if lcp in buckets and buckets[lcp]:
            continue  # actually a brand-with-branches case; claimed earlier
        syn_groups[lcp].extend(members)

    # Merge in the refined-synthesizable from pass 1 (Places that were
    # attributed to a too-short brand but really need a synthesized brand).
    for prefix, members in refined_synth.items():
        if prefix in syn_groups:
            existing_ids = {m.id for m in syn_groups[prefix]}
            syn_groups[prefix].extend(m for m in members if m.id not in existing_ids)
        else:
            syn_groups[prefix].extend(members)

    # Trim trailing short tokens from synthesizable prefixes — typically the
    # leading article of a location name ("Al", "El", "Il" in Arabic place
    # names). E.g. "bespecta al" (where every branch is at "Bespecta - Al X")
    # should synthesize as "Bespecta" not "Bespecta Al". Re-bucket because
    # multiple pre-trim prefixes can collapse to the same trimmed prefix.
    # Words that almost always start a *location* (city, mall, festival) but
    # almost never end a *brand name*. Trim them off the LCP tail.
    LOCATION_SUFFIX_WORDS = {
        "city", "mall", "centre", "center", "walk", "festival", "plaza",
        "square", "bay", "downtown", "marina", "beach", "souk", "park",
        "gallery", "hills", "lakes", "towers", "residence", "residences",
        "village", "island", "promenade", "courtyard", "boulevard",
    }
    trimmed_syn_groups: dict[str, list] = defaultdict(list)
    for prefix, members in syn_groups.items():
        toks = prefix.split()
        # Drop trailing 1-2 char tokens (apostrophe artifacts, "al"/"el") AND
        # known location-prefix words.
        while toks and (len(toks[-1]) < 3 or toks[-1] in LOCATION_SUFFIX_WORDS):
            toks.pop()
        new_prefix = " ".join(toks)
        if not new_prefix:
            continue
        # Re-bucket but de-dup by Place.id.
        existing_ids = {m.id for m in trimmed_syn_groups[new_prefix]}
        trimmed_syn_groups[new_prefix].extend(m for m in members if m.id not in existing_ids)
    syn_groups = trimmed_syn_groups

    for prefix, members in sorted(syn_groups.items()):
        if len(members) < 2:
            continue
        prefix_tokens = prefix.split()
        if any(len(t) < 2 for t in prefix_tokens):
            continue  # any sub-2-char token is junk (apostrophe-s artifact)
        # Require either >=2 meaningful tokens OR a single >=6 char token
        # (catches single-word brands like "Bespecta" or "Pastaria").
        if len(prefix_tokens) < 2 and len(prefix) < 6:
            continue
        if len(prefix.replace(" ", "")) < 6:
            continue
        members.sort(key=lambda p: p.id)
        branch_src: set[str] = set()
        for m in members:
            branch_src |= m._source_programs
        branches_entertainer_only = bool(branch_src) and branch_src.issubset({"entertainer"})

        confidence = "high" if branches_entertainer_only else "medium"
        auto_merge = branches_entertainer_only

        cluster = {
            "cluster_id": prefix,
            "kind": "synthesizable_branches",
            "brand_id": None,
            "branch_ids": [m.id for m in members],
            "brand_source_programs": [],
            "branch_source_programs": sorted(branch_src),
            "places": [
                {
                    "id": p.id, "slug": p.slug, "name": p.name,
                    "discount_count": p._discount_count,
                    "source_programs": sorted(p._source_programs),
                    "lat": float(p.lat) if p.lat is not None else None,
                    "lng": float(p.lng) if p.lng is not None else None,
                    "area": p.area, "address": p.address, "website": p.website,
                    "logo_url_override": p.logo_url_override,
                    "is_brand": False,
                }
                for p in members
            ],
            "confidence": confidence,
            "auto_merge": auto_merge,
            # No canonical yet — merger will synthesize one if auto_merge.
            "suggested_canonical_id": None,
            "notes": f"no brand-level Place; synthesize one named {prefix.title()!r}",
        }
        clusters.append(cluster)
        for m in members:
            claimed_norms.add(normalize_name(m.name))

    # ---- Pass 3: cross_source pairs (existing v1 logic) ----
    for key, members in buckets.items():
        if len(members) < 2:
            continue
        if key in claimed_norms:
            continue  # already covered by brand_with_branches

        members.sort(key=lambda p: p.id)
        a, b = members[0], members[1]
        signals = _score_pair(a, b, _haversine_m, lambda p: p.logo_domain)
        areas_match = bool(a.area) and a.area.strip().lower() == (b.area or "").strip().lower()
        confidence, auto_merge = _confidence_of(signals, areas_match, len(key))

        needs_review_note = ""
        if len(members) > 2:
            auto_merge = False
            confidence = "medium" if confidence == "high" else confidence
            needs_review_note = f"cluster has {len(members)} places; auto-merge disabled"

        kind = "cross_source" if signals["complementary_sources"] else "likely_branches"

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
        if confidence == "low" and not include_low:
            continue
        if kind == "likely_branches" and confidence != "high":
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
    auto_loser_total = 0
    for c in clusters:
        by_conf[c["confidence"]] += 1
        by_kind[c["kind"]] += 1
        if c["auto_merge"]:
            auto += 1
            if c["kind"] == "brand_with_branches":
                auto_loser_total += len(c["branch_ids"])
            elif c["kind"] == "synthesizable_branches":
                auto_loser_total += len(c["branch_ids"])
            else:
                auto_loser_total += len(c["places"]) - 1
    print(f"\nwrote {DEST}")
    print(f"  clusters total: {len(clusters)}")
    for k in ("high", "medium", "low"):
        print(f"  confidence={k}: {by_conf.get(k, 0)}")
    for k in ("brand_with_branches", "synthesizable_branches", "cross_source", "likely_branches"):
        print(f"  kind={k}: {by_kind.get(k, 0)}")
    print(f"  auto-merge eligible: {auto} clusters, {auto_loser_total} loser Places")
    return len(clusters)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--include-low", action="store_true",
                        help="include low-confidence clusters in the output")
    args = parser.parse_args()
    _boot_django()
    audit(include_low=args.include_low)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
