"""One-shot data migration: wipe the original demo seed (Pickl, Atlantis,
Burj Khalifa, etc. with their fabricated promo codes and percentages) and
insert Mondoux as the first verified entry. Runs once on prod when this
migration is first applied; reverse is a no-op (we don't restore demos)."""

from django.db import migrations


PLACE_SPEC = {
    "slug": "mondoux",
    "name": "Mondoux",
    "category": "restaurant",
    "area": "Multiple locations",
    "address": (
        "Bluewaters Island; "
        "Dubai Creek Harbour (South Tower 1 Promenade, Ras Al Khor); "
        "The Beach JBR; "
        "The Dubai Mall (Dubai Fountain View)."
    ),
    "phone": "+971 50 137 2814",
    "website": "https://mondoux.ae",
    "description": (
        "French-inspired all-day café known for healthy bowls, crepes, "
        "macarons and chocolate, with four Dubai branches: Bluewaters, "
        "Dubai Creek Harbour, The Beach JBR, and The Dubai Mall.\n\n"
        "Opening hours (all branches): Mon–Thu 8:00 — 23:30, "
        "Fri–Sun 8:00 — 00:30."
    ),
    "is_published": True,
}

DISCOUNT_SPEC = {
    "slug": "up-to-25-cashback-via-the-mondoux-app",
    "title": "Up to 25% cashback via the Mondoux app",
    "discount_type": "percentage",
    "percentage": 25,
    "source_program": "in_house",
    "description": (
        "Members of Mondoux's own loyalty program earn 10%–25% cashback "
        "on every purchase, redeemable as in-app credit on future visits. "
        "Includes exclusive offers, gifts and invitations to VIP events.\n\n"
        "How to enrol: download the Mondoux app (iOS or Android) from "
        "the link on https://mondoux.ae/loyalty-program/ and register."
    ),
    "terms": (
        "Cashback rate varies based on Mondoux's tier rules — see the app "
        "for the current schedule. Valid at all four Dubai branches."
    ),
    "is_active": True,
    "is_featured": True,
}


def replace_demo_seed_with_mondoux(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")

    Discount.objects.all().delete()
    Place.objects.all().delete()

    place = Place.objects.create(**PLACE_SPEC)
    Discount.objects.create(place=place, **DISCOUNT_SPEC)


def reverse_noop(apps, schema_editor):
    """Rolling back this migration won't restore the demo seed."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0003_add_discount_source_program"),
        ("places", "0002_place_is_members_only"),
    ]

    operations = [
        migrations.RunPython(replace_demo_seed_with_mondoux, reverse_noop),
    ]
