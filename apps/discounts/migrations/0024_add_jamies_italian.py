"""Add Jamie's Italian (Dubai Hills Mall) — Entertainer venue that was
missing from the original sitemap-based imports (0015–0017). The venue is
on theentertainerme.com (m=64156, slug=jamies-italian) but its URL was not
in the sitemap snapshot we fetched.

Idempotent: get_or_create on slug. Reverse drops both rows.
"""
from django.db import migrations


PLACE_SLUG = "jamies-italian"
DISCOUNT_SLUG = "ent-jamies-italian"
URL = "https://www.theentertainerme.com/outlets/jamies-italian/detail"


def add_jamies(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")
    place, _ = Place.objects.get_or_create(
        slug=PLACE_SLUG,
        defaults={
            "name": "Jamie's Italian",
            "category": "restaurant",
            "area": "Dubai Hills",
            "address": "",
            "phone": "",
            "website": "https://www.jamiesitalian.ae",
            "description": (
                "Jamie's Italian — casual-dining restaurant at Dubai Hills "
                "Mall, loved for regional Italian dishes, freshly made "
                "pasta, antipasti, hand-tossed pizzas, grills and salads."
            ),
            "is_published": True,
        },
    )
    Discount.objects.update_or_create(
        slug=DISCOUNT_SLUG,
        defaults={
            "place": place,
            "title": "Buy One Get One Free at Jamie's Italian via The Entertainer",
            "discount_type": "bogo",
            "source_program": "entertainer",
            "description": (
                "Use The Entertainer to redeem a Buy One Get One Free deal "
                "at Jamie's Italian, Dubai Hills Mall. Active on the 2026 "
                "Entertainer subscription."
            ),
            "terms": (
                "Requires an active Entertainer membership. Redeem in-app "
                "before settling the bill — see the Entertainer outlet "
                "page for current terms and exclusions."
            ),
            "external_url": URL,
            "is_active": True,
            "is_featured": False,
        },
    )


def remove_jamies(apps, schema_editor):
    Discount = apps.get_model("discounts", "Discount")
    Place = apps.get_model("places", "Place")
    Discount.objects.filter(slug=DISCOUNT_SLUG).delete()
    Place.objects.filter(slug=PLACE_SLUG).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0023_seed_fazaa_offers"),
    ]

    operations = [
        migrations.RunPython(add_jamies, remove_jamies),
    ]
