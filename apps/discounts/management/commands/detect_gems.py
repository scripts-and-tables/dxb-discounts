"""Score every live Discount and auto-flag the top N% as is_featured=True.

Used by the dedup-style detect-gems skill. Deterministic scorer; running
twice produces the same set, and we never unset an existing is_featured
row (manual curator picks stay sticky).

Usage:
  python manage.py detect_gems                 # dry-run, prints top 20
  python manage.py detect_gems --apply         # flip is_featured for top 5%
  python manage.py detect_gems --top-percent 1 --apply   # tighter cut
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.discounts.models import Discount, DiscountType
from apps.places.models import Place


# Text signals — substring matches on lowercase title + description.
POSITIVE_KEYWORDS = ("exclusive", "vip", "premium", "complimentary", "limited")
NEGATIVE_KEYWORDS = ("up to",)


@dataclass
class ScoreRow:
    discount_id: int
    score: int
    breakdown: dict[str, int]
    title: str
    place_name: str
    source: str


def _value_score(d: Discount) -> tuple[int, dict[str, int]]:
    """Points from offer-intrinsic value (percentage, BOGO, fixed price)."""
    breakdown: dict[str, int] = {}
    if d.percentage is not None:
        if d.percentage >= 50:
            breakdown["pct50+"] = 5
        elif d.percentage >= 30:
            breakdown["pct30-49"] = 3
        elif d.percentage >= 20:
            breakdown["pct20-29"] = 1
    if d.discount_type == DiscountType.BOGO:
        breakdown["bogo"] = 2
    if d.fixed_price_aed is not None:
        v = float(d.fixed_price_aed)
        if v >= 100:
            breakdown["fixed100+"] = 5
        elif v >= 50:
            breakdown["fixed50+"] = 3
        elif v >= 25:
            breakdown["fixed25+"] = 1
    return sum(breakdown.values()), breakdown


def _brand_score_for_place(p: Place, place_stats: dict[int, dict]) -> tuple[int, dict[str, int]]:
    breakdown: dict[str, int] = {}
    stats = place_stats[p.id]
    n_programs = len(stats["sources"])
    if n_programs >= 3:
        breakdown["3+programs"] = 3
    elif n_programs == 2:
        breakdown["2programs"] = 1
    n_offers = stats["count"]
    if n_offers >= 10:
        breakdown["10+offers"] = 2
    elif n_offers >= 5:
        breakdown["5+offers"] = 1
    if p.logo_url_override:
        breakdown["logo_override"] = 1
    return sum(breakdown.values()), breakdown


def _text_score(d: Discount) -> tuple[int, dict[str, int]]:
    breakdown: dict[str, int] = {}
    haystack = f"{d.title or ''} {d.description or ''}".lower()
    for kw in POSITIVE_KEYWORDS:
        if kw in haystack:
            breakdown[f"+{kw}"] = 1
            break
    if any(kw in haystack for kw in NEGATIVE_KEYWORDS):
        breakdown["-up_to"] = -2
    return sum(breakdown.values()), breakdown


def score_all(discounts: list[Discount], place_by_id: dict[int, Place],
              place_stats: dict[int, dict]) -> list[ScoreRow]:
    rows: list[ScoreRow] = []
    for d in discounts:
        v, vb = _value_score(d)
        place = place_by_id[d.place_id]
        b, bb = _brand_score_for_place(place, place_stats)
        t, tb = _text_score(d)
        total = v + b + t
        breakdown = {**vb, **bb, **tb}
        rows.append(ScoreRow(
            discount_id=d.id, score=total, breakdown=breakdown,
            title=d.title, place_name=place.name,
            source=d.source_program or "",
        ))
    return rows


class Command(BaseCommand):
    help = "Score every live Discount; auto-flag top N% as is_featured=True."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="actually write is_featured=True to the DB")
        parser.add_argument("--top-percent", type=float, default=5.0,
                            help="percentile threshold (default 5.0)")

    def handle(self, *args, apply: bool, top_percent: float, **kwargs):
        live = list(
            Discount.objects.live().select_related("place")
            .only("id", "title", "description", "percentage", "fixed_price_aed",
                  "discount_type", "is_featured", "source_program", "place__id",
                  "place__name", "place__logo_url_override")
        )
        self.stdout.write(f"loaded {len(live)} live Discounts")

        place_ids = {d.place_id for d in live}
        place_by_id: dict[int, Place] = {p.id: p for p in
            Place.objects.filter(id__in=place_ids).only("id", "name", "logo_url_override")}

        # Pre-compute per-place stats: distinct source_programs, discount count.
        place_stats: dict[int, dict] = defaultdict(lambda: {"sources": set(), "count": 0})
        for d in live:
            place_stats[d.place_id]["count"] += 1
            if d.source_program:
                place_stats[d.place_id]["sources"].add(d.source_program)

        rows = score_all(live, place_by_id, place_stats)
        # Sort by score desc, tiebreak by discount_id desc (newer offers
        # win ties — they're more likely to reflect current marketing).
        rows.sort(key=lambda r: (-r.score, -r.discount_id))

        # Cap strictly at top N% by count. Score ties at the boundary are
        # broken by discount_id (deterministic). This avoids a 1,055-tie
        # at score=6 inflating the cut from 5% to 9%.
        n_total = len(rows)
        n_threshold = max(1, int(n_total * top_percent / 100))
        gem_rows = [r for r in rows[:n_threshold] if r.score > 0]
        gem_ids = {r.discount_id for r in gem_rows}
        cutoff_score = gem_rows[-1].score if gem_rows else 0

        # Distribution summary.
        dist = Counter(r.score for r in rows)
        self.stdout.write("\nScore distribution (top buckets):")
        for score in sorted(dist.keys(), reverse=True)[:12]:
            self.stdout.write(f"  score={score:>3}: {dist[score]} discounts")

        self.stdout.write(f"\nTop {top_percent}% threshold: score >= {cutoff_score}")
        self.stdout.write(f"Featured candidates: {len(gem_rows)} ({len(gem_rows)*100/n_total:.1f}% of live)")

        self.stdout.write("\nTop 20 candidates:")
        def _safe(s: str) -> str:
            # Windows cp1252 console chokes on most unicode in offer titles;
            # ascii-roundtrip with '?' replacement so the summary is printable.
            return (s or "").encode("ascii", errors="replace").decode("ascii")
        for r in rows[:20]:
            bd = " ".join(f"{k}+{v}" if v > 0 else f"{k}{v}" for k, v in r.breakdown.items())
            self.stdout.write(
                f"  score={r.score:>3}  {_safe(r.title)[:35]:<35}  "
                f"@ {_safe(r.place_name)[:25]:<25}  [{r.source}]  {bd}"
            )

        # Idempotency check: how many candidates are already featured?
        already_featured_ids = set(
            Discount.objects.filter(id__in=gem_ids, is_featured=True).values_list("id", flat=True)
        )
        to_flip = gem_ids - already_featured_ids
        self.stdout.write(
            f"\nOf {len(gem_ids)} candidates: {len(already_featured_ids)} already featured, "
            f"{len(to_flip)} would be newly flipped."
        )

        if not apply:
            self.stdout.write(self.style.WARNING("\nDRY RUN — no DB writes. Pass --apply to set is_featured."))
            return

        if to_flip:
            Discount.objects.filter(id__in=to_flip).update(is_featured=True)
        self.stdout.write(self.style.SUCCESS(
            f"\nflipped is_featured=True on {len(to_flip)} discounts "
            f"(total featured now: {Discount.objects.filter(is_featured=True).count()})"
        ))
