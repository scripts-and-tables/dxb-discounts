"""Seed the database with sample places and discounts.

Idempotent: running multiple times keeps the catalog stable.

Usage:
    python manage.py seed             # add or update sample data
    python manage.py seed --reset     # delete all places & discounts first
"""

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.discounts.models import Discount, DiscountProgram, DiscountType
from apps.places.models import Category, Place


PLACES = [
    {
        "key": "reform-social-and-grill",
        "name": "Reform Social & Grill",
        "category": Category.RESTAURANT,
        "area": "The Lakes",
        "address": "The Lakes Club, The Lakes",
        "phone": "+971 4 454 2638",
        "website": "https://reformsocialgrill.ae",
        "description": "British gastropub with a leafy garden terrace, popular for Friday brunch.",
    },
    {
        "key": "pickl",
        "name": "Pickl",
        "category": Category.RESTAURANT,
        "area": "JLT",
        "address": "Cluster T, JLT",
        "phone": "",
        "website": "https://pickl.com",
        "description": "Smashed burgers, loaded fries and shakes.",
    },
    {
        "key": "tom-and-serg",
        "name": "Tom & Serg",
        "category": Category.RESTAURANT,
        "area": "Al Quoz",
        "address": "Warehouse 15, Al Quoz",
        "phone": "+971 4 386 7474",
        "website": "https://www.tomandserg.com",
        "description": "All-day cafe in a converted Al Quoz warehouse — flat whites, brunch and pasta.",
    },
    {
        "key": "zuma-dubai",
        "name": "Zuma Dubai",
        "category": Category.RESTAURANT,
        "area": "DIFC",
        "address": "Gate Village 06, DIFC",
        "phone": "+971 4 425 5660",
        "website": "https://zumarestaurant.com/locations/dubai",
        "description": "Contemporary Japanese izakaya with a robata grill and sushi counter.",
    },
    {
        "key": "img-worlds-of-adventure",
        "name": "IMG Worlds of Adventure",
        "category": Category.ATTRACTION,
        "area": "City of Arabia",
        "address": "Sheikh Mohammed Bin Zayed Road, City of Arabia",
        "phone": "+971 4 403 8888",
        "website": "https://www.imgworlds.com",
        "description": "The world's largest indoor theme park, with Marvel and Cartoon Network zones.",
    },
    {
        "key": "aquaventure-waterpark",
        "name": "Aquaventure Waterpark",
        "category": Category.ATTRACTION,
        "area": "Palm Jumeirah",
        "address": "Atlantis, The Palm",
        "phone": "+971 4 426 0000",
        "website": "https://www.atlantis.com/dubai/atlantis-aquaventure",
        "description": "Record-breaking waterpark with marine animal experiences at Atlantis.",
    },
    {
        "key": "at-the-top-burj-khalifa",
        "name": "At the Top, Burj Khalifa",
        "category": Category.ATTRACTION,
        "area": "Downtown",
        "address": "Burj Khalifa, Downtown Dubai",
        "phone": "+971 4 888 8888",
        "website": "https://www.burjkhalifa.ae",
        "description": "Observation deck experiences on levels 124, 125 and 148 of the Burj Khalifa.",
    },
    {
        "key": "atlantis-the-palm",
        "name": "Atlantis, The Palm",
        "category": Category.HOTEL,
        "area": "Palm Jumeirah",
        "address": "Crescent Road, Palm Jumeirah",
        "phone": "+971 4 426 2000",
        "website": "https://www.atlantis.com/dubai",
        "description": "Iconic ocean-themed resort at the apex of Palm Jumeirah.",
    },
    {
        "key": "five-palm-jumeirah",
        "name": "FIVE Palm Jumeirah",
        "category": Category.HOTEL,
        "area": "Palm Jumeirah",
        "address": "Palm Jumeirah, West Crescent",
        "phone": "+971 4 455 9888",
        "website": "https://www.fivehotelsandresorts.com/dubai/palm-jumeirah",
        "description": "Energetic beach resort known for its pool parties and rooftop dining.",
    },
    {
        "key": "talise-spa",
        "name": "Talise Spa",
        "category": Category.RETAIL,
        "area": "Madinat Jumeirah",
        "address": "Madinat Jumeirah",
        "phone": "+971 4 366 6818",
        "website": "https://www.jumeirah.com",
        "description": "Award-winning spa offering massages, hammam, and signature wellness rituals.",
    },
    {
        "key": "sephora-dubai-mall",
        "name": "Sephora Dubai Mall",
        "category": Category.RETAIL,
        "area": "Downtown",
        "address": "Lower Ground, The Dubai Mall",
        "phone": "+971 800 26800",
        "website": "https://www.sephora.ae",
        "description": "Beauty department with international brands, fragrance, and skincare.",
    },
    {
        "key": "gymnation",
        "name": "GymNation",
        "category": Category.RETAIL,
        "area": "JLT",
        "address": "Mövenpick Hotel JLT",
        "phone": "+971 800 49646286",
        "website": "https://gymnation.com",
        "description": "24/7 affordable gym chain with classes and personal training.",
    },
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
        "place": "reform-social-and-grill",
        "title": "30% off à la carte dinner Sunday to Thursday",
        "discount_type": DiscountType.PERCENTAGE,
        "percentage": 30,
        "description": "Enjoy 30% off the food bill on à la carte dinner from Sunday to Thursday, 6pm–10pm.",
        "terms": "Not valid on public holidays. Cannot be combined with other offers.",
        "valid_from": date(2026, 1, 1),
        "valid_until": date(2026, 12, 31),
        "is_featured": True,
    },
    {
        "place": "reform-social-and-grill",
        "title": "AED 199 unlimited Friday brunch",
        "discount_type": DiscountType.FIXED_PRICE,
        "fixed_price_aed": "199.00",
        "description": "Three hours of unlimited soft drinks plus a sharing roast for AED 199 per person.",
        "terms": "Friday only, 1pm–4pm. Children under 6 dine free.",
    },
    {
        "place": "pickl",
        "title": "2-for-1 burgers every Tuesday",
        "discount_type": DiscountType.BOGO,
        "description": "Buy any signature burger and get a second one free, all day Tuesday.",
        "terms": "Dine-in only. Lower-priced burger is free.",
        "is_featured": True,
    },
    {
        "place": "pickl",
        "title": "15% off first online order",
        "discount_type": DiscountType.PROMO_CODE,
        "promo_code": "PICKLNEW",
        "description": "First-time online customers get 15% off their order.",
        "terms": "One use per customer. Minimum order AED 50.",
    },
    {
        "place": "tom-and-serg",
        "title": "20% off weekday breakfast",
        "discount_type": DiscountType.PERCENTAGE,
        "percentage": 20,
        "description": "20% off any breakfast item Sunday to Thursday before 11am.",
        "terms": "Not valid on weekends or public holidays.",
    },
    {
        "place": "tom-and-serg",
        "title": "AED 99 lunch combo",
        "discount_type": DiscountType.FIXED_PRICE,
        "fixed_price_aed": "99.00",
        "description": "Pasta or salad plus a soft drink for AED 99 weekday lunches.",
        "terms": "Sunday–Thursday, 12pm–3pm. Dine-in only.",
    },
    {
        "place": "zuma-dubai",
        "title": "Business lunch at AED 165",
        "discount_type": DiscountType.FIXED_PRICE,
        "fixed_price_aed": "165.00",
        "description": "Two-course business lunch at AED 165 per person, weekdays only.",
        "terms": "Sunday–Thursday, 12pm–3pm. Drinks not included.",
        "is_featured": True,
    },
    {
        "place": "zuma-dubai",
        "title": "2-for-1 sushi rolls at the bar",
        "discount_type": DiscountType.BOGO,
        "description": "Buy any signature roll at the sushi counter and get a second one free.",
        "terms": "Sushi bar only. Sunday and Tuesday, 6pm–8pm.",
    },
    {
        "place": "img-worlds-of-adventure",
        "title": "25% off second ticket",
        "discount_type": DiscountType.PERCENTAGE,
        "percentage": 25,
        "description": "Buy a full-price IMG Worlds ticket online and get 25% off a second one.",
        "terms": "Online bookings only. Cannot be combined with annual passes.",
    },
    {
        "place": "aquaventure-waterpark",
        "title": "AED 299 day pass — Aquaventure",
        "discount_type": DiscountType.FIXED_PRICE,
        "fixed_price_aed": "299.00",
        "description": "Full-day waterpark access from AED 299 when booked online in advance.",
        "terms": "Subject to availability. Children below 1.2m enter at a reduced rate.",
        "is_featured": True,
    },
    {
        "place": "at-the-top-burj-khalifa",
        "title": "10% off At the Top tickets with code",
        "discount_type": DiscountType.PROMO_CODE,
        "promo_code": "DXBVIEWS10",
        "description": "Use code DXBVIEWS10 at checkout for 10% off non-prime hour tickets.",
        "terms": "Excludes sunset slots. Online bookings only.",
        "valid_until": date(2026, 9, 30),
    },
    {
        "place": "atlantis-the-palm",
        "title": "30% off best flexible rate",
        "discount_type": DiscountType.PERCENTAGE,
        "percentage": 30,
        "description": "Save 30% on Atlantis room rates when booking 14 days in advance.",
        "terms": "Non-refundable. Aquaventure access included.",
        "is_featured": True,
    },
    {
        "place": "atlantis-the-palm",
        "title": "Stay 4, pay 3",
        "discount_type": DiscountType.BOGO,
        "description": "Book four consecutive nights at Atlantis and only pay for three.",
        "terms": "Cheapest night is free. Subject to availability and minimum stay rules.",
    },
    {
        "place": "five-palm-jumeirah",
        "title": "Pool day pass AED 250 with redemption",
        "discount_type": DiscountType.FIXED_PRICE,
        "fixed_price_aed": "250.00",
        "description": "Beach and pool access at FIVE Palm Jumeirah from AED 250 with full redemption on food & drink.",
        "terms": "Weekdays only. Subject to availability.",
    },
    {
        "place": "talise-spa",
        "title": "20% off 60-minute massage",
        "discount_type": DiscountType.PERCENTAGE,
        "percentage": 20,
        "description": "Save 20% on any 60-minute signature massage Sunday to Wednesday.",
        "terms": "Pre-booking required. Not valid on weekends.",
    },
    {
        "place": "sephora-dubai-mall",
        "title": "AED 50 off when you spend AED 250",
        "discount_type": DiscountType.PROMO_CODE,
        "promo_code": "DXB50",
        "description": "Take AED 50 off any in-store purchase of AED 250 or more.",
        "terms": "Not valid on luxury fragrance. One use per customer.",
        "valid_until": date(2026, 8, 31),
    },
    {
        "place": "gymnation",
        "title": "First month free for new members",
        "discount_type": DiscountType.PROMO_CODE,
        "promo_code": "DXBFITNESS",
        "description": "New members get their first month of unlimited access free.",
        "terms": "12-month commitment required. New members only.",
        "is_featured": True,
    },
    {
        "place": "gymnation",
        "title": "Bring a friend free for a week",
        "discount_type": DiscountType.BOGO,
        "description": "Active members can sign in a friend each day for a full week.",
        "terms": "Friend must register at reception. Photo ID required.",
    },
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
    help = "Populate the database with sample places and discounts."

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
