"""Add Caribou Coffee Place + three Discounts (Fazaa, Esaad, Caribou Perks)
on first apply. Idempotent via update_or_create on (slug) for Place and
(place, title) for Discount, so re-running is safe."""

from django.db import migrations


PLACE_SPEC = {
    "slug": "caribou-coffee",
    "name": "Caribou Coffee",
    "category": "restaurant",
    "area": "Multiple locations across the UAE",
    "address": (
        "40+ Dubai outlets including The Dubai Mall (2nd floor), Times "
        "Square Center, Burjuman, Deira City Centre, Dubai Media City, "
        "and DIFC. Operated under M.H. Alshaya Co. franchise."
    ),
    "phone": "",
    "website": "https://www.cariboucoffee.com",
    "description": (
        "American specialty coffee chain founded in 1992 in Edina, "
        "Minnesota, with a strong presence in the UAE through 40+ "
        "outlets across Dubai and additional branches in Abu Dhabi and "
        "the northern emirates. Known for hand-crafted espresso drinks, "
        "the signature Mint Condition cooler, blueberry muffins, and "
        "the Caribou Perks loyalty program."
    ),
    "is_published": True,
}

DISCOUNT_SPECS = [
    {
        "slug": "up-to-30-off-with-fazaa-card",
        "title": "Up to 30% off with Fazaa Card",
        "discount_type": "percentage",
        "percentage": 30,
        "source_program": "fazaa",
        "description": (
            "Fazaa cardholders get up to 30% off at Caribou Coffee outlets "
            "across the UAE. Show your Fazaa card or scan via the Fazaa app "
            "at checkout to apply the discount."
        ),
        "terms": (
            "Discount tier may vary by item category. See the official Fazaa "
            "offer at fazaa.ae/offers/view/caribou-coffee for current T&Cs. "
            "Cardholders only; one transaction at a time."
        ),
        "is_active": True,
        "is_featured": True,
    },
    {
        "slug": "20-off-with-esaad-card",
        "title": "20% off with Esaad Card",
        "discount_type": "percentage",
        "percentage": 20,
        "source_program": "esaad",
        "description": (
            "Esaad cardholders get 20% off at Caribou Coffee outlets in "
            "the UAE. Present your Esaad card or scan via the Esaad app "
            "at checkout."
        ),
        "terms": (
            "Typically applies to beverages. Verify the live offer on the "
            "Esaad app before redeeming. Cardholders only."
        ),
        "is_active": True,
        "is_featured": False,
    },
    {
        "slug": "caribou-perks-earn-points-for-free-drinks",
        "title": "Caribou Perks: earn points for free drinks",
        "discount_type": "percentage",
        "percentage": 10,
        "source_program": "in_house",
        "description": (
            "Caribou's own loyalty program. Earn points on every purchase "
            "via the Caribou Rewards app (iOS or Android), then redeem for "
            "free drinks, bakery items and size upgrades. Members also get "
            "a sign-up bonus and exclusive seasonal offers.\n\n"
            "How to enrol: download the Caribou Rewards app from the UAE "
            "App Store or Google Play and register."
        ),
        "terms": (
            "Points-based program — the 10% headline is an indicative "
            "effective rebate; actual value depends on which rewards you "
            "redeem. Valid at all participating UAE outlets."
        ),
        "is_active": True,
        "is_featured": False,
    },
]


def add_caribou_coffee(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")

    place, _ = Place.objects.update_or_create(
        slug=PLACE_SPEC["slug"],
        defaults={k: v for k, v in PLACE_SPEC.items() if k != "slug"},
    )

    for spec in DISCOUNT_SPECS:
        Discount.objects.update_or_create(
            slug=spec["slug"],
            defaults={**{k: v for k, v in spec.items() if k != "slug"}, "place": place},
        )


def remove_caribou_coffee(apps, schema_editor):
    """Reverse: remove the Caribou rows added by this migration."""
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")

    Discount.objects.filter(slug__in=[s["slug"] for s in DISCOUNT_SPECS]).delete()
    Place.objects.filter(slug=PLACE_SPEC["slug"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0004_replace_demo_seed_with_mondoux"),
    ]

    operations = [
        migrations.RunPython(add_caribou_coffee, remove_caribou_coffee),
    ]
