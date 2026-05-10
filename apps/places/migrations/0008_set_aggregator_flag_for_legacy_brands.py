"""Flag brand-level legacy Places as aggregators and drop their orphan ent-* generics.

Migrations 0015-0017 in the discounts app created one generic Discount per
venue with slug `ent-{place_slug}` (title "Buy One Get One Free at <name>
via The Entertainer"). The new ingest (`ingest_offers --source entertainer`)
later created one Discount per actual offer attached to outlet-level Places
(e.g. "Jones the Grocer (JBR)"). For multi-branch brands the legacy
brand-level Place ("Jones the Grocer") was left holding the generic row
with no per-offer rows, since `consolidate_legacy_offers` skipped the
ambiguous multi-branch case.

This data migration sweeps that residue: where a legacy Place has at least
one sibling branch whose normalized name starts with the legacy name, set
`aggregates_branches=True` and delete the generic ent-* Discount. The
detail view rolls up branch Discount rows in lieu of the removed generic.

Idempotent: re-running is a no-op once the brand has zero remaining ent-*
rows. Reverse leaves data unchanged (we don't recreate generic rows).

Legacy Places without any matching branch are left alone — their generic
ent-* row remains as a brand-level fallback discount."""
import re

from django.db import migrations


_PUNCTUATION_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")
_STOPWORDS = {
    "the", "a", "an", "by", "at", "of", "and",
    "restaurant", "restaurants", "cafe", "café", "kafe", "kafé", "bar", "lounge",
    "kitchen", "grill", "house", "club", "dubai", "uae", "emirates",
}


def normalize_name(name: str) -> str:
    """Mirror of apps.places.matching.normalize_name. Inlined so the migration
    is self-contained and not affected by future refactors of that module."""
    if not name:
        return ""
    n = name.lower()
    n = _PUNCTUATION_RE.sub(" ", n)
    n = _WHITESPACE_RE.sub(" ", n).strip()
    tokens = [t for t in n.split() if t and t not in _STOPWORDS]
    return " ".join(tokens)


def flag_brand_aggregators(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")

    # Pre-index every published Place's normalized name → list of (id, normalized_name).
    all_norms: list[tuple[int, str]] = [
        (p.id, normalize_name(p.name))
        for p in Place.objects.filter(is_published=True).only("id", "name")
    ]

    legacy_qs = (
        Discount.objects
        .filter(slug__startswith="ent-", source_program="entertainer")
        .select_related("place")
    )

    flagged = 0
    deleted = 0
    skipped_no_branch = 0

    for d in legacy_qs.iterator():
        place = d.place
        brand_norm = normalize_name(place.name)
        if not brand_norm:
            skipped_no_branch += 1
            continue
        # Skip if this Place itself already has new entertainer-* rows; the
        # main consolidate-from-the-management-command flow handles that and
        # we don't want to interfere here.
        if Discount.objects.filter(place=place, slug__startswith="entertainer-").exists():
            d.delete()
            deleted += 1
            continue
        # Look for sibling branches by normalized name prefix.
        has_branch = any(
            pid != place.id and n and n.startswith(brand_norm + " ")
            for pid, n in all_norms
        )
        if not has_branch:
            skipped_no_branch += 1
            continue
        if not place.aggregates_branches:
            place.aggregates_branches = True
            place.save(update_fields=["aggregates_branches"])
            flagged += 1
        d.delete()
        deleted += 1

    print(f"  brand aggregators flagged: {flagged}")
    print(f"  legacy ent-* discounts deleted: {deleted}")
    print(f"  legacy without branch siblings (kept as fallback): {skipped_no_branch}")


def noop_reverse(apps, schema_editor):
    """Reversing leaves the DB as-is. We don't recreate deleted generic rows
    or unset the aggregator flag — both are safe no-ops."""
    return


class Migration(migrations.Migration):

    dependencies = [
        ("places", "0007_place_aggregates_branches"),
        ("discounts", "0031_seed_referrals"),
    ]

    operations = [
        migrations.RunPython(flag_brand_aggregators, noop_reverse),
    ]
