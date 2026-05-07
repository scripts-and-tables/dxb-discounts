"""Add Dubai partner hotels from Elite Club's public UAE brochure PDF.

Source: store.eliteclub.global/wp-content/uploads/2024/10/EC-UAE-BROCHURE
(89 pages — sections per emirate). Pages 4..45 are Dubai venues; one
hotel per page with Room/Food/Spa/Gym/Beverage benefit percentages.
The headline % stored on the Discount is the highest of those (FOOD
preferred since dining is the most relatable filter).

Idempotent: get_or_create on Place (preserves any existing rows that
share a slug — for example a hotel already imported from Supper Club),
update_or_create on Discount.

Reverse drops only the rows we added here, matched by slug.
"""

from django.db import migrations


PLACES = [
    {
        'slug': 'ja-lake-view-hotel',
        'name': 'JA Lake View Hotel',
        'area': 'Dubai',
        'page': 4,
    },
    {
        'slug': 'ja-beach-hotel',
        'name': 'JA Beach Hotel',
        'area': 'Dubai',
        'page': 5,
    },
    {
        'slug': 'ja-palm-tree-court',
        'name': 'JA Palm Tree Court',
        'area': 'Dubai',
        'page': 6,
    },
    {
        'slug': 'ja-ocean-view-hotel',
        'name': 'JA Ocean View Hotel',
        'area': 'Dubai',
        'page': 7,
    },
    {
        'slug': 'the-manor-by-ja',
        'name': 'The Manor by JA',
        'area': 'Dubai',
        'page': 8,
    },
    {
        'slug': 'ja-hatta-fort-hotel',
        'name': 'JA Hatta Fort Hotel',
        'area': 'Dubai',
        'page': 9,
    },
    {
        'slug': 'movenpick-hotel-jumeirah-beach',
        'name': 'Movenpick Hotel Jumeirah Beach',
        'area': 'Dubai',
        'page': 11,
    },
    {
        'slug': 'movenpick-grand-al-bustan-dubai',
        'name': 'Movenpick Grand Al Bustan Dubai',
        'area': 'Dubai',
        'page': 12,
    },
    {
        'slug': 'movenpick-hotel-apartments-downtown-dubai',
        'name': 'Movenpick Hotel Apartments Downtown Dubai',
        'area': 'Dubai',
        'page': 13,
    },
    {
        'slug': 'grand-millennium-hotel-dubai',
        'name': 'Grand Millennium Hotel Dubai',
        'area': 'Dubai',
        'page': 14,
    },
    {
        'slug': 'holiday-inn-suites-dubai-science-park',
        'name': 'Holiday Inn & Suites Dubai Science Park',
        'area': 'Dubai',
        'page': 15,
    },
    {
        'slug': 'swiss-tel-al-murooj',
        'name': 'Swissôtel Al Murooj',
        'area': 'Dubai',
        'page': 16,
    },
    {
        'slug': 'al-habtoor-polo-resort',
        'name': 'Al Habtoor Polo Resort',
        'area': 'Dubai',
        'page': 17,
    },
    {
        'slug': 'renaissance-business-bay-hotel',
        'name': 'Renaissance Business Bay Hotel',
        'area': 'Dubai',
        'page': 18,
    },
    {
        'slug': 'avani-deira-dubai-hotel',
        'name': 'AVANI Deira Dubai Hotel',
        'area': 'Dubai',
        'page': 19,
    },
    {
        'slug': 'radisson-blu-hotel-dubai-waterfront',
        'name': 'Radisson Blu Hotel Dubai Waterfront',
        'area': 'Dubai',
        'page': 20,
    },
    {
        'slug': 'radisson-blu-hotel-dubai-canal-view',
        'name': 'Radisson Blu Hotel Dubai Canal View',
        'area': 'Dubai',
        'page': 21,
    },
    {
        'slug': 'canal-central-hotel-business-bay',
        'name': 'Canal Central Hotel Business Bay',
        'area': 'Dubai',
        'page': 22,
    },
    {
        'slug': 'royal-central-hotel-the-palm',
        'name': 'Royal Central Hotel The Palm',
        'area': 'Dubai',
        'page': 23,
    },
    {
        'slug': 'c-central-resort-the-palm',
        'name': 'C Central Resort The Palm',
        'area': 'Dubai',
        'page': 24,
    },
    {
        'slug': 'the-h-dubai',
        'name': 'The H Dubai',
        'area': 'Dubai',
        'page': 25,
    },
    {
        'slug': 'metropolitan-hotel-dubai',
        'name': 'Metropolitan Hotel Dubai',
        'area': 'Dubai',
        'page': 26,
    },
    {
        'slug': 'millennium-plaza-downtown-hotel',
        'name': 'Millennium Plaza Downtown Hotel',
        'area': 'Dubai',
        'page': 27,
    },
    {
        'slug': 'm-venpick-hotel-jumeirah-village-triangle',
        'name': 'Mövenpick Hotel Jumeirah Village Triangle',
        'area': 'Dubai',
        'page': 28,
    },
    {
        'slug': 'kempinski-hotel-residences-palm-jumeirah',
        'name': 'Kempinski Hotel & Residences Palm Jumeirah',
        'area': 'Dubai',
        'page': 29,
    },
    {
        'slug': 'crowne-plaza-dubai-marina',
        'name': 'Crowne Plaza Dubai Marina',
        'area': 'Dubai',
        'page': 30,
    },
    {
        'slug': 'avani-palm-view-dubai-hotel-suites',
        'name': 'Avani Palm View Dubai Hotel & Suites',
        'area': 'Dubai',
        'page': 31,
    },
    {
        'slug': 'wyndham-residences-the-palm',
        'name': 'Wyndham Residences The Palm',
        'area': 'Dubai',
        'page': 32,
    },
    {
        'slug': 'the-dubai-edition',
        'name': 'The Dubai Edition',
        'area': 'Dubai',
        'page': 33,
    },
    {
        'slug': 'fairmont-dubai',
        'name': 'Fairmont Dubai',
        'area': 'Dubai',
        'page': 34,
    },
    {
        'slug': 'grand-cosmopolitan-hotel-dubai',
        'name': 'Grand Cosmopolitan Hotel Dubai',
        'area': 'Dubai',
        'page': 35,
    },
    {
        'slug': 'the-retreat-palm-mgallery-by-sofitel',
        'name': 'The Retreat Palm MGallery by Sofitel',
        'area': 'Dubai',
        'page': 36,
    },
    {
        'slug': 'marriott-marquis-dubai',
        'name': 'Marriott Marquis Dubai',
        'area': 'Dubai',
        'page': 37,
    },
    {
        'slug': 'hilton-dubai-creek-hotel-residences',
        'name': 'Hilton Dubai Creek Hotel & Residences',
        'area': 'Dubai',
        'page': 38,
    },
    {
        'slug': 'pullman-downtown-dubai',
        'name': 'Pullman Downtown Dubai',
        'area': 'Dubai',
        'page': 39,
    },
    {
        'slug': 'th8-palm-dubai',
        'name': 'Th8 Palm Dubai',
        'area': 'Dubai',
        'page': 40,
    },
    {
        'slug': 'suha-park-luxury-hotel-apartments',
        'name': 'Suha Park Luxury Hotel Apartments',
        'area': 'Dubai',
        'page': 42,
    },
    {
        'slug': 'hilton-garden-inn-dubai-al-mina',
        'name': 'Hilton Garden Inn Dubai Al Mina',
        'area': 'Dubai',
        'page': 43,
    },
    {
        'slug': 'time-oak-hotel-suites',
        'name': 'TIME Oak Hotel & Suites',
        'area': 'Dubai',
        'page': 44,
    },
    {
        'slug': 'time-grand-plaza-hotel',
        'name': 'TIME Grand Plaza Hotel',
        'area': 'Dubai',
        'page': 45,
    },
]


DISCOUNTS = [
    {
        'place_slug': 'ja-lake-view-hotel',
        'discount_slug': 'ec-ja-lake-view-hotel',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '30% Room, 50% Food, 25% Beverage, 30% Spa, 30% Gym',
    },
    {
        'place_slug': 'ja-beach-hotel',
        'discount_slug': 'ec-ja-beach-hotel',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '30% Room, 50% Food, 25% Beverage, 30% Spa, 30% Gym',
    },
    {
        'place_slug': 'ja-palm-tree-court',
        'discount_slug': 'ec-ja-palm-tree-court',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '30% Room, 50% Food, 25% Beverage, 30% Spa, 30% Gym',
    },
    {
        'place_slug': 'ja-ocean-view-hotel',
        'discount_slug': 'ec-ja-ocean-view-hotel',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '30% Room, 50% Food, 25% Beverage, 30% Spa, 30% Gym',
    },
    {
        'place_slug': 'the-manor-by-ja',
        'discount_slug': 'ec-the-manor-by-ja',
        'title': 'Up to 25% off via Elite Club',
        'headline_pct': 25,
        'bullet': '30% Room, 25% Food, 25% Beverage',
    },
    {
        'place_slug': 'ja-hatta-fort-hotel',
        'discount_slug': 'ec-ja-hatta-fort-hotel',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '30% Room, 50% Food, 25% Beverage, 30% Spa, 30% Gym',
    },
    {
        'place_slug': 'movenpick-hotel-jumeirah-beach',
        'discount_slug': 'ec-movenpick-hotel-jumeirah-beach',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '10% Room, 50% Food, 20% Beverage, 20% Spa, 25% Gym',
    },
    {
        'place_slug': 'movenpick-grand-al-bustan-dubai',
        'discount_slug': 'ec-movenpick-grand-al-bustan-dubai',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '20% Room, 50% Food, 20% Beverage, 20% Spa, 30% Gym',
    },
    {
        'place_slug': 'movenpick-hotel-apartments-downtown-dubai',
        'discount_slug': 'ec-movenpick-hotel-apartments-downtown-dubai',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '15% Room, 50% Food, 20% Beverage, 20% Spa, 20% Gym',
    },
    {
        'place_slug': 'grand-millennium-hotel-dubai',
        'discount_slug': 'ec-grand-millennium-hotel-dubai',
        'title': 'Up to 20% off via Elite Club',
        'headline_pct': 20,
        'bullet': '20% Room, 20% Spa, 20% Gym',
    },
    {
        'place_slug': 'holiday-inn-suites-dubai-science-park',
        'discount_slug': 'ec-holiday-inn-suites-dubai-science-park',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '10% Room, 50% Food, 20% Beverage, 20% Spa',
    },
    {
        'place_slug': 'swiss-tel-al-murooj',
        'discount_slug': 'ec-swiss-tel-al-murooj',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '8% Room, 50% Food, 20% Beverage, 25% Spa, 15% Gym',
    },
    {
        'place_slug': 'al-habtoor-polo-resort',
        'discount_slug': 'ec-al-habtoor-polo-resort',
        'title': 'Up to 30% off via Elite Club',
        'headline_pct': 30,
        'bullet': '20% Room, 30% Food, 30% Beverage, 20% Spa',
    },
    {
        'place_slug': 'renaissance-business-bay-hotel',
        'discount_slug': 'ec-renaissance-business-bay-hotel',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '50% Spa',
    },
    {
        'place_slug': 'avani-deira-dubai-hotel',
        'discount_slug': 'ec-avani-deira-dubai-hotel',
        'title': 'Up to 20% off via Elite Club',
        'headline_pct': 20,
        'bullet': '20% Room',
    },
    {
        'place_slug': 'radisson-blu-hotel-dubai-waterfront',
        'discount_slug': 'ec-radisson-blu-hotel-dubai-waterfront',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '20% Room, 50% Food, 20% Beverage, 20% Spa, 20% Gym',
    },
    {
        'place_slug': 'radisson-blu-hotel-dubai-canal-view',
        'discount_slug': 'ec-radisson-blu-hotel-dubai-canal-view',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '20% Room, 50% Food, 20% Beverage, 20% Gym',
    },
    {
        'place_slug': 'canal-central-hotel-business-bay',
        'discount_slug': 'ec-canal-central-hotel-business-bay',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '15% Room, 50% Food, 20% Beverage, 20% Spa, 20% Gym',
    },
    {
        'place_slug': 'royal-central-hotel-the-palm',
        'discount_slug': 'ec-royal-central-hotel-the-palm',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '15% Room, 50% Food, 20% Beverage',
    },
    {
        'place_slug': 'c-central-resort-the-palm',
        'discount_slug': 'ec-c-central-resort-the-palm',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '15% Room, 50% Food, 20% Beverage, 20% Spa, 20% Gym',
    },
    {
        'place_slug': 'the-h-dubai',
        'discount_slug': 'ec-the-h-dubai',
        'title': 'Up to 25% off via Elite Club',
        'headline_pct': 25,
        'bullet': '20% Room, 25% Food, 25% Beverage, 20% Spa, 20% Gym',
    },
    {
        'place_slug': 'metropolitan-hotel-dubai',
        'discount_slug': 'ec-metropolitan-hotel-dubai',
        'title': 'Up to 25% off via Elite Club',
        'headline_pct': 25,
        'bullet': '20% Room, 25% Food, 25% Beverage, 20% Gym',
    },
    {
        'place_slug': 'millennium-plaza-downtown-hotel',
        'discount_slug': 'ec-millennium-plaza-downtown-hotel',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '25% Room, 50% Food, 20% Beverage, 20% Gym',
    },
    {
        'place_slug': 'm-venpick-hotel-jumeirah-village-triangle',
        'discount_slug': 'ec-m-venpick-hotel-jumeirah-village-triangle',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '15% Room, 50% Food, 25% Beverage, 20% Spa, 20% Gym',
    },
    {
        'place_slug': 'kempinski-hotel-residences-palm-jumeirah',
        'discount_slug': 'ec-kempinski-hotel-residences-palm-jumeirah',
        'title': 'Up to 20% off via Elite Club',
        'headline_pct': 20,
        'bullet': '20% Room, 20% Food, 20% Beverage, 20% Spa, 20% Gym',
    },
    {
        'place_slug': 'crowne-plaza-dubai-marina',
        'discount_slug': 'ec-crowne-plaza-dubai-marina',
        'title': 'Up to 25% off via Elite Club',
        'headline_pct': 25,
        'bullet': '25% Spa',
    },
    {
        'place_slug': 'avani-palm-view-dubai-hotel-suites',
        'discount_slug': 'ec-avani-palm-view-dubai-hotel-suites',
        'title': 'Up to 20% off via Elite Club',
        'headline_pct': 20,
        'bullet': '10% Room, 20% Food, 20% Beverage',
    },
    {
        'place_slug': 'wyndham-residences-the-palm',
        'discount_slug': 'ec-wyndham-residences-the-palm',
        'title': 'Up to 25% off via Elite Club',
        'headline_pct': 25,
        'bullet': '10% Room, 25% Food, 25% Beverage, 10% Gym',
    },
    {
        'place_slug': 'the-dubai-edition',
        'discount_slug': 'ec-the-dubai-edition',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '50% Spa',
    },
    {
        'place_slug': 'fairmont-dubai',
        'discount_slug': 'ec-fairmont-dubai',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '50% Spa',
    },
    {
        'place_slug': 'grand-cosmopolitan-hotel-dubai',
        'discount_slug': 'ec-grand-cosmopolitan-hotel-dubai',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '50% Spa',
    },
    {
        'place_slug': 'the-retreat-palm-mgallery-by-sofitel',
        'discount_slug': 'ec-the-retreat-palm-mgallery-by-sofitel',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '50% Spa',
    },
    {
        'place_slug': 'marriott-marquis-dubai',
        'discount_slug': 'ec-marriott-marquis-dubai',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '50% Spa',
    },
    {
        'place_slug': 'hilton-dubai-creek-hotel-residences',
        'discount_slug': 'ec-hilton-dubai-creek-hotel-residences',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '50% Spa',
    },
    {
        'place_slug': 'pullman-downtown-dubai',
        'discount_slug': 'ec-pullman-downtown-dubai',
        'title': 'Up to 50% off via Elite Club',
        'headline_pct': 50,
        'bullet': '50% Spa',
    },
    {
        'place_slug': 'th8-palm-dubai',
        'discount_slug': 'ec-th8-palm-dubai',
        'title': 'Up to 25% off via Elite Club',
        'headline_pct': 25,
        'bullet': '25% Gym',
    },
    {
        'place_slug': 'suha-park-luxury-hotel-apartments',
        'discount_slug': 'ec-suha-park-luxury-hotel-apartments',
        'title': 'Up to 20% off via Elite Club',
        'headline_pct': 20,
        'bullet': '20% off',
    },
    {
        'place_slug': 'hilton-garden-inn-dubai-al-mina',
        'discount_slug': 'ec-hilton-garden-inn-dubai-al-mina',
        'title': 'Up to 20% off via Elite Club',
        'headline_pct': 20,
        'bullet': '20% off',
    },
    {
        'place_slug': 'time-oak-hotel-suites',
        'discount_slug': 'ec-time-oak-hotel-suites',
        'title': 'Up to 20% off via Elite Club',
        'headline_pct': 20,
        'bullet': '20% off',
    },
    {
        'place_slug': 'time-grand-plaza-hotel',
        'discount_slug': 'ec-time-grand-plaza-hotel',
        'title': 'Up to 20% off via Elite Club',
        'headline_pct': 20,
        'bullet': '20% off',
    },
]


def add_eliteclub(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")

    place_by_slug = {}
    for spec in PLACES:
        place, _ = Place.objects.get_or_create(
            slug=spec["slug"],
            defaults={
                "name": spec["name"],
                "category": "hotel",
                "area": spec["area"],
                "address": "",
                "phone": "",
                "website": "",
                "description": (
                    f'{spec["name"]} — Dubai partner of Elite Club. Members '
                    f'get tiered discounts on rooms, dining, spa and more — '
                    f'see the EC UAE brochure on store.eliteclub.global for '
                    f'current offers.'
                ),
                "is_published": True,
            },
        )
        place_by_slug[spec["slug"]] = place

    for d in DISCOUNTS:
        place = place_by_slug.get(d["place_slug"])
        if place is None:
            continue
        Discount.objects.update_or_create(
            slug=d["discount_slug"],
            defaults={
                "place": place,
                "title": d["title"][:200],
                "discount_type": "percentage",
                "percentage": d["headline_pct"],
                "source_program": "elite_club",
                "description": (
                    f'Elite Club members benefit from: {d["bullet"]}. '
                    f'Each percentage applies to the named category — book '
                    f'via the Elite Club app to redeem.'
                ),
                "terms": (
                    "Discount tiers depend on Elite Club membership level "
                    "(Silver / Gold / Platinum). See the EC UAE brochure "
                    "for the latest offer matrix and exclusions."
                ),
                "external_url": "https://store.eliteclub.global/en/uae/",
                "is_active": True,
                "is_featured": False,
            },
        )


def remove_eliteclub(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")
    Discount.objects.filter(slug__in=[d["discount_slug"] for d in DISCOUNTS]).delete()
    Place.objects.filter(slug__in=[p["slug"] for p in PLACES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0017_more_entertainer_venues"),
        ("places", "0004_seed_experiences_and_autotag"),
    ]

    operations = [
        migrations.RunPython(add_eliteclub, remove_eliteclub),
    ]
