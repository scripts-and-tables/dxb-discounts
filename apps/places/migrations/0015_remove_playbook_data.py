"""One-shot: delete all Playbook-sourced Discount rows and unpublish any
Place whose only offers came from Playbook.

Background: Playbook (my-playbook.com) turned out to be a venue-discovery
app, not a discount program. Their `Highlights` field is a marketing
calendar (Ladies Night, Afternoon Tea, Breakfast Buffet, ...) — not
offers. We had ingested 5,046 of these as Discount rows with
`source_program=playbook`, all with `percentage=NULL` and
`fixed_price_aed=NULL` because there was no discount value to extract.

What this migration does on prod:
1. Bulk-deletes every Discount with `source_program="playbook"`.
2. For every published Place that now has zero active Discounts,
   sets `is_published=False` (soft delete). Their Place rows stay in
   the DB so admin can still find them.

Idempotent: re-running is a no-op (no Playbook discounts to delete,
and any Place that became visible-discount-less stays unpublished).

Reverse: noop. We removed `ingest_playbook` in the same commit, so
re-creating the rows would require re-introducing the function plus
data/playbook_search_enriched.json (still present for icon/coord
backfill, not for ingest).
"""
from django.db import migrations


def remove_playbook(apps, schema_editor):
    Discount = apps.get_model("discounts", "Discount")
    Place = apps.get_model("places", "Place")

    # 1. Delete misclassified Discount rows.
    qs = Discount.objects.filter(source_program="playbook")
    n_discounts = qs.count()
    qs.delete()
    print(f"[0015_remove_playbook] deleted {n_discounts} Discount rows.")

    # 2. Unpublish Places that now have zero active Discounts. We exclude
    # Places that already aren't published, so re-runs are quick.
    candidates = Place.objects.filter(is_published=True).exclude(
        discounts__is_active=True
    ).distinct()
    n_places = candidates.count()
    # bulk_update can't update a queryset filter with a constant — use a
    # raw .update() instead. (Place.is_published has no auto_now hooks.)
    Place.objects.filter(id__in=list(candidates.values_list("id", flat=True))).update(
        is_published=False,
    )
    print(f"[0015_remove_playbook] unpublished {n_places} Places (no remaining active discounts).")


def noop_reverse(apps, schema_editor):
    """Reverse leaves the DB as-is."""
    return


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("places", "0014_consolidate_brand_branches_production"),
        ("discounts", "0033_seed_referrals"),
    ]

    operations = [
        migrations.RunPython(remove_playbook, noop_reverse),
    ]
