"""Seed the database with curated places and discounts.

Idempotent: running multiple times keeps the catalog stable.

Usage:
    python manage.py seed             # add or update entries
    python manage.py seed --reset     # delete all places & discounts first
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.discounts.models import Discount, DiscountProgram, DiscountType
from apps.places.models import Category, Place


PLACES = [
    {
        "key": "mondoux",
        "name": "Mondoux",
        "category": Category.RESTAURANT,
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
    },
    {
        "key": "caribou-coffee",
        "name": "Caribou Coffee",
        "category": Category.RESTAURANT,
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
    },
]

DISCOUNTS = [
    {
        "place": "mondoux",
        "title": "Up to 25% cashback via the Mondoux app",
        "discount_type": DiscountType.PERCENTAGE,
        "percentage": 25,
        "source_program": DiscountProgram.IN_HOUSE,
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
        "is_featured": True,
    },
    {
        "place": "caribou-coffee",
        "title": "Up to 30% off with Fazaa Card",
        "discount_type": DiscountType.PERCENTAGE,
        "percentage": 30,
        "source_program": DiscountProgram.FAZAA,
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
        "is_featured": True,
    },
    {
        "place": "caribou-coffee",
        "title": "20% off with Esaad Card",
        "discount_type": DiscountType.PERCENTAGE,
        "percentage": 20,
        "source_program": DiscountProgram.ESAAD,
        "description": (
            "Esaad cardholders get 20% off at Caribou Coffee outlets in "
            "the UAE. Present your Esaad card or scan via the Esaad app "
            "at checkout."
        ),
        "terms": (
            "Typically applies to beverages. Verify the live offer on the "
            "Esaad app before redeeming. Cardholders only."
        ),
    },
    {
        "place": "caribou-coffee",
        "title": "Caribou Perks: earn points for free drinks",
        "discount_type": DiscountType.PERCENTAGE,
        "percentage": 10,
        "source_program": DiscountProgram.IN_HOUSE,
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
    },
]


class Command(BaseCommand):
    help = "Populate the database with curated places and discounts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all places and discounts before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            self.stdout.write("Resetting places & discounts…")
            Discount.objects.all().delete()
            Place.objects.all().delete()

        place_by_key: dict[str, Place] = {}
        for spec in PLACES:
            key = spec["key"]
            place, created = Place.objects.update_or_create(
                slug=key,
                defaults={
                    "name": spec["name"],
                    "category": spec["category"],
                    "area": spec["area"],
                    "address": spec["address"],
                    "phone": spec["phone"],
                    "website": spec["website"],
                    "description": spec["description"],
                    "is_published": True,
                },
            )
            place_by_key[key] = place
            self.stdout.write(("+ " if created else "= ") + place.name)

        for spec in DISCOUNTS:
            place = place_by_key[spec["place"]]
            title = spec["title"]
            defaults = {
                "discount_type": spec["discount_type"],
                "percentage": spec.get("percentage"),
                "fixed_price_aed": spec.get("fixed_price_aed"),
                "promo_code": spec.get("promo_code", ""),
                "source_program": spec.get("source_program", ""),
                "description": spec["description"],
                "terms": spec.get("terms", ""),
                "valid_from": spec.get("valid_from"),
                "valid_until": spec.get("valid_until"),
                "is_active": True,
                "is_featured": spec.get("is_featured", False),
            }
            discount, created = Discount.objects.update_or_create(
                place=place,
                title=title,
                defaults=defaults,
            )
            self.stdout.write(("+ " if created else "= ") + f"{discount.title} @ {place.name}")

        self.stdout.write(self.style.SUCCESS(
            f"Seed complete: {Place.objects.count()} places, {Discount.objects.count()} discounts."
        ))
