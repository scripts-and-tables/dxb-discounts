"""Collapse the three Hamptons Cafe branch Places into a single brand Place.

After 0039 the catalog had three published Hamptons outlets:
- The Hamptons Cafe — Emirates Hills (id 10851 on local; 11648 on prod
  at last check) with a Zomato Gold 10% discount
- The Hamptons Cafe — Umm Suqeim with the same discount
- The Hamptons Cafe (Jumeirah Islands) — older Place, no active discount

User feedback: these read as duplicates on the home page's
`?programs=zomato` filter (three near-identical cards). The
dedup-places skill correctly refuses to auto-merge them (they're
likely_branches per its scorer), but the user wants visual aggregation.

This migration:
  1. Creates a single brand-level Place "The Hamptons Cafe" with
     aggregates_branches=True, so its detail page rolls up any
     remaining branch Discounts.
  2. Gives the brand its own Zomato Gold 10% discount so it surfaces
     on the home `?programs=zomato` filter.
  3. Soft-deletes the three branch Places (is_published=False). Their
     existing Discount rows stay attached but are excluded from
     `Discount.live()` because `place__is_published=True` is part of
     the live filter — so the home and place-detail pages no longer
     show the duplicate cards.

This loses per-branch identity in the catalog, which is acceptable for
v1: all three branches currently have the same Zomato Gold offer, and
if they diverge later we can re-publish individual branches and add
branch-specific Discounts.
"""
from django.db import migrations


BRAND_SLUG = "the-hamptons-cafe"
BRAND_DESCRIPTION = (
    "The Hamptons Cafe is a Mediterranean café and brunch destination with "
    "multiple Dubai outlets — at Jumeirah Islands Pavilion (Emirates Hills), "
    "Madinat Jumeirah Souk Madinat (Umm Suqeim), and Jumeirah Islands. Known "
    "for its garden-terrace setting, all-day breakfast and weekend brunch."
)
BRAND_AREA = "Multiple locations"

# Branch Places to soft-delete. Slugs are stable across local + prod
# (set in migrations 0037 and the pre-existing 9940 Place).
BRANCH_SLUGS = [
    "the-hamptons-cafe-emirates-hills",
    "the-hamptons-cafe-umm-suqeim",
    "the-hamptons-cafe-jumeirah-islands",
]

ZOMATO_DESCRIPTION = (
    "Zomato Gold members get a flat 10% off the food bill at any "
    "Hamptons Cafe Dubai outlet — no booking required, no minimum spend. "
    "Just show your Zomato Gold membership before paying. Annual Gold "
    "membership is ~AED 149 (often free for HSBC, FAB and Mastercard "
    "cardholders). Sign up via the Zomato app."
)
ZOMATO_TERMS = (
    "Must be an active Zomato Gold member; verify the venue's current "
    "Gold partner status in the Zomato app — Zomato rotates partner "
    "lists periodically. Applies to the food bill, typically excluding "
    "alcohol and service charge. Not combinable with other discounts "
    "(Entertainer, Fazaa, etc.) at the same bill. Full T&Cs at "
    "zomato.com/dubai/gold."
)


def aggregate_hamptons(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")

    # 1. Create or update the brand Place.
    brand, _ = Place.objects.update_or_create(
        slug=BRAND_SLUG,
        defaults={
            "name": "The Hamptons Cafe",
            "category": "restaurant",
            "area": BRAND_AREA,
            "description": BRAND_DESCRIPTION,
            "aggregates_branches": True,
            "is_published": True,
            "is_members_only": False,
        },
    )

    # 2. Brand-level Zomato Gold discount.
    Discount.objects.update_or_create(
        slug=f"zomato-flat-{BRAND_SLUG}",
        defaults={
            "place": brand,
            "title": "The Hamptons Cafe — Flat 10% off with Zomato Gold",
            "discount_type": "percentage",
            "percentage": 10,
            "source_program": "zomato",
            "description": ZOMATO_DESCRIPTION,
            "terms": ZOMATO_TERMS,
            "external_url": "https://www.zomato.com/dubai/restaurants/the-hamptons-cafe",
            "is_members_only": False,
            "is_active": True,
        },
    )

    # 3. Soft-delete the branch Places. Their existing Discounts stay
    #    attached but are filtered out by Discount.live() due to the
    #    place__is_published=True constraint.
    Place.objects.filter(slug__in=BRANCH_SLUGS).update(is_published=False)


def restore_hamptons(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")
    # Republish the branches
    Place.objects.filter(slug__in=BRANCH_SLUGS).update(is_published=True)
    # Remove the brand-level rows
    Discount.objects.filter(slug=f"zomato-flat-{BRAND_SLUG}").delete()
    Place.objects.filter(slug=BRAND_SLUG).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0039_disambiguate_hamptons_branches"),
        ("places", "0018_rerun_dedup_with_relaxed_rules"),
    ]

    operations = [
        migrations.RunPython(aggregate_hamptons, restore_hamptons),
    ]
