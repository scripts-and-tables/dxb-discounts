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
