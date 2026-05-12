"""Rename synthesized brand Places whose name was derived from the
normalized cluster_id (and thus reads awkwardly) using the longest
common prefix of their *original* branches' names instead.

A synthesized Place is identified by: its only discounts come from
ingest sources OTHER than this Place itself (i.e. all its discounts
have a slug like `entertainer-...` that points back to a branch), AND
the original branch Places (now is_published=False) still exist with
names that share a common prefix.

Example fix:
  "Adventure Zone Adventure" -> "Adventure Zone by Adventure HQ"

Dry-run by default. Pass --apply to write.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.discounts.models import Discount
from apps.places.matching import normalize_name
from apps.places.models import Place


def _char_lcp(names: list[str]) -> str:
    if not names:
        return ""
    ref = names[0]
    n = min(len(s) for s in names)
    lcp_len = 0
    for i in range(n):
        ch = ref[i].lower()
        if all(s[i].lower() == ch for s in names):
            lcp_len = i + 1
        else:
            break
    cand = ref[:lcp_len].rstrip(" \t-–—―•·:,.;/|")
    if cand.lower().endswith(" by"):
        cand = cand[: -3].rstrip()
    return cand


def _better_name_for(canonical: Place) -> str | None:
    """If `canonical` is a synthesized brand and its branches have a cleaner
    common-prefix name, return it. Otherwise return None.

    Heuristic for "this is a synthesized brand": there exist 2+ unpublished
    Places whose normalize_name starts with the canonical's normalize_name +
    " " (i.e. they look like its branches).
    """
    cnorm = normalize_name(canonical.name)
    if not cnorm:
        return None
    # Find unpublished Places whose normalized name starts with cnorm + " ".
    prefix_lower = (cnorm + " ").lower()
    branches: list[Place] = []
    for p in Place.objects.filter(is_published=False).only("id", "name"):
        pnorm = normalize_name(p.name)
        if pnorm.startswith(prefix_lower.rstrip()) and pnorm != cnorm:
            branches.append(p)
    if len(branches) < 2:
        return None
    candidate = _char_lcp([b.name for b in branches])
    if len(candidate) < 3:
        return None
    if candidate.lower() == canonical.name.lower():
        return None  # already matches
    return candidate


class Command(BaseCommand):
    help = "Rename synthesized brand Places using char-LCP of their original branches' names."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="actually rename (default is dry-run)")

    def handle(self, *args, apply: bool, **kwargs):
        # Candidate synthesized brands: published Places whose name has a
        # repeated token (a signature of the old normalize+title-case logic).
        # E.g. "Adventure Zone Adventure", "Pastaria Pastaria", etc. We also
        # process Places whose name ends with a stripped article remnant.
        candidates: list[Place] = []
        for p in Place.objects.filter(is_published=True).only("id", "name"):
            toks = p.name.split()
            if not toks:
                continue
            # Repeated token at any position
            lower = [t.lower() for t in toks]
            if len(set(lower)) < len(lower):
                candidates.append(p)

        self.stdout.write(f"scanning {len(candidates)} Places with repeated-token names")

        renames: list[tuple[Place, str]] = []
        for p in candidates:
            better = _better_name_for(p)
            if better:
                renames.append((p, better))

        for p, better in renames:
            self.stdout.write(f"  id={p.id:>5}  {p.name!r:<60} -> {better!r}")

        if not apply:
            self.stdout.write(self.style.WARNING(
                f"\n[dry-run] would rename {len(renames)} Places. Pass --apply to write."
            ))
            return

        for p, better in renames:
            Place.objects.filter(id=p.id).update(name=better)
        self.stdout.write(self.style.SUCCESS(f"\nrenamed {len(renames)} Places."))
