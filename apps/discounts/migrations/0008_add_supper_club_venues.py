"""First batch of Supper Club ME partner venues in Dubai.

Supper Club's catalog on supperclubme.com is rendered by JavaScript and
not extractable by static scraping; the full 200+ venue list lives behind
their app. This migration adds the 11 Dubai venues that surfaced through
Google's index of supperclubme.com (site: search) with their offer
headlines. More can be added via the admin once the user has the full
list from the Supper Club app.

Idempotent: update_or_create on slug. Reverse deletes the rows added
here (matched by slug).
"""

from django.db import migrations


PLACES = [
    {
        "slug": "the-hide-jumeirah-al-qasr",
        "name": "The Hide",
        "category": "restaurant",
        "area": "Madinat Jumeirah",
        "address": "Jumeirah Al Qasr, Madinat Jumeirah",
        "website": "https://www.jumeirah.com",
        "description": "Award-winning steakhouse at Jumeirah Al Qasr in Madinat Jumeirah, known for premium cuts and an elegant atmosphere.",
    },
    {
        "slug": "fluid-beach-club-th8-palm",
        "name": "Fluid Beach Club",
        "category": "hotel",
        "area": "Palm Jumeirah",
        "address": "Th8 The Palm, Palm Jumeirah",
        "website": "https://th8palm.com",
        "description": "Beach club at Th8 The Palm with an infinity pool, Palm West Beach access, daybeds and a relaxed all-day food and drinks menu.",
    },
    {
        "slug": "mimis-pool-club-five-jumeirah-village",
        "name": "Mimi's Pool Club",
        "category": "hotel",
        "area": "Jumeirah Village",
        "address": "FIVE Jumeirah Village Dubai",
        "website": "https://www.fivehotelsandresorts.com",
        "description": "Adults-only pool club on the rooftop of FIVE Jumeirah Village, with daybeds, cocktail bar and skyline views over JVC.",
    },
    {
        "slug": "prime68-jw-marriott-marquis",
        "name": "Prime68",
        "category": "restaurant",
        "area": "Business Bay",
        "address": "JW Marriott Marquis, Business Bay",
        "website": "https://www.marriott.com",
        "description": "Contemporary American steakhouse on the 68th floor of the JW Marriott Marquis, with sweeping views over Downtown Dubai and the Burj Khalifa.",
    },
    {
        "slug": "great-british-restaurant-dukes-the-palm",
        "name": "Great British Restaurant",
        "category": "restaurant",
        "area": "Palm Jumeirah",
        "address": "Dukes The Palm, Palm Jumeirah",
        "website": "https://www.dukesthepalm.com",
        "description": "Classic British dining at Dukes The Palm. The Saturday Britpop Brunch comes with Lazy River and infinity-pool access overlooking Dubai Marina.",
    },
    {
        "slug": "crescendo-anantara-the-palm",
        "name": "Crescendo",
        "category": "restaurant",
        "area": "Palm Jumeirah",
        "address": "Anantara The Palm Dubai Resort, Palm Jumeirah",
        "website": "https://www.anantara.com",
        "description": "International all-day buffet restaurant at Anantara The Palm Dubai, with live cooking stations spanning Asian, Middle Eastern and Western cuisines.",
    },
    {
        "slug": "jw-kitchen-jw-marriott-marina",
        "name": "JW Kitchen",
        "category": "restaurant",
        "area": "Dubai Marina",
        "address": "JW Marriott Marina, Dubai Marina",
        "website": "https://www.marriott.com",
        "description": "International buffet restaurant at the JW Marriott Marina, popular for its Saturday brunch and dinner buffet packages.",
    },
    {
        "slug": "solo-raffles-dubai",
        "name": "Solo",
        "category": "restaurant",
        "area": "Wafi",
        "address": "Raffles Dubai, Wafi",
        "website": "https://www.raffles.com",
        "description": "Italian restaurant at Raffles Dubai serving classic regional dishes, wood-fired pizzas and an extensive wine selection.",
    },
    {
        "slug": "ikandy-shangri-la-dubai",
        "name": "iKandy",
        "category": "hotel",
        "area": "Sheikh Zayed Road",
        "address": "Shangri-La Dubai, Sheikh Zayed Road",
        "website": "https://www.shangri-la.com",
        "description": "Pool and lounge bar on the 6th floor of the Shangri-La Dubai, with cabanas, sushi and an extensive cocktail list.",
    },
    {
        "slug": "conrad-dubai-pool",
        "name": "Conrad Dubai Pool",
        "category": "hotel",
        "area": "Sheikh Zayed Road",
        "address": "Conrad Dubai, Sheikh Zayed Road",
        "website": "https://www.hilton.com",
        "description": "Outdoor temperature-controlled pool at Conrad Dubai with cabanas, F&B service and views over Sheikh Zayed Road.",
    },
    {
        "slug": "jw-marriott-marquis-pool",
        "name": "JW Marriott Marquis Pool",
        "category": "hotel",
        "area": "Business Bay",
        "address": "JW Marriott Marquis, Business Bay",
        "website": "https://www.marriott.com",
        "description": "Outdoor pool at the JW Marriott Marquis with full-day access, F&B credit and views of the Burj Khalifa skyline.",
    },
]


DISCOUNTS = [
    {
        "place_slug": "the-hide-jumeirah-al-qasr",
        "slug": "the-hide-25-off-via-supper-club",
        "title": "25% off the total bill via Supper Club",
        "percentage": 25,
        "description": "Supper Club ME members get 25% off the total bill at The Hide steakhouse, Jumeirah Al Qasr.",
        "terms": "Valid for Supper Club ME members. Discount applied at the venue — show the offer in your Supper Club app.",
    },
    {
        "place_slug": "fluid-beach-club-th8-palm",
        "slug": "fluid-beach-club-30-off-via-supper-club",
        "title": "30% off the total bill via Supper Club",
        "percentage": 30,
        "description": "Supper Club ME members get 30% off the total bill at Fluid Beach Club, Th8 The Palm.",
        "terms": "Valid for Supper Club ME members. Discount applied at the venue.",
    },
    {
        "place_slug": "mimis-pool-club-five-jumeirah-village",
        "slug": "mimis-pool-fb-credit-via-supper-club",
        "title": "Pool access with F&B credit via Supper Club",
        "percentage": 30,
        "description": "Supper Club ME members get exclusive pool access with food & beverage credit at Mimi's Pool Club, FIVE Jumeirah Village.",
        "terms": "F&B credit varies by package. Book through the Supper Club app for the current offer.",
    },
    {
        "place_slug": "prime68-jw-marriott-marquis",
        "slug": "prime68-25-off-a-la-carte-via-supper-club",
        "title": "25% off the à la carte menu via Supper Club",
        "percentage": 25,
        "description": "Supper Club ME members get 25% off à la carte at Prime68, the rooftop steakhouse on the 68th floor of the JW Marriott Marquis.",
        "terms": "À la carte only. Valid for Supper Club ME members.",
    },
    {
        "place_slug": "great-british-restaurant-dukes-the-palm",
        "slug": "gbr-50-off-britpop-brunch-via-supper-club",
        "title": "Up to 50% off Saturday Britpop Brunch via Supper Club",
        "percentage": 50,
        "description": "Supper Club ME members save up to 50% on the Saturday Britpop Brunch at GBR, Dukes The Palm — includes Lazy River and infinity-pool access.",
        "terms": "Saturday only. Bubbly package: was AED 445, member price AED 222.50. Other packages also discounted; book via Supper Club.",
    },
    {
        "place_slug": "crescendo-anantara-the-palm",
        "slug": "crescendo-50-off-brunch-via-supper-club",
        "title": "50% off brunch via Supper Club",
        "percentage": 50,
        "description": "Supper Club ME members and their guests get 50% off brunch packages at Crescendo, Anantara The Palm Dubai.",
        "terms": "Valid for Supper Club ME members.",
    },
    {
        "place_slug": "jw-kitchen-jw-marriott-marina",
        "slug": "jw-kitchen-50-off-brunch-via-supper-club",
        "title": "50% off Saturday brunch via Supper Club",
        "percentage": 50,
        "description": "Supper Club ME members get 50% off Saturday brunch packages at JW Kitchen, JW Marriott Marina. Soft beverage package: was AED 310, member price AED 155 per person.",
        "terms": "Saturday only. 50% off also applies to the international dinner buffet on selected nights.",
    },
    {
        "place_slug": "solo-raffles-dubai",
        "slug": "solo-50-off-saturday-brunch-via-supper-club",
        "title": "50% off Saturday brunch from AED 149 via Supper Club",
        "percentage": 50,
        "description": "Supper Club ME members enjoy 50% off Saturday brunch at Solo, Raffles Dubai, with packages starting at AED 149.",
        "terms": "Saturday only. Member price starts at AED 149 per person.",
    },
    {
        "place_slug": "ikandy-shangri-la-dubai",
        "slug": "ikandy-pool-aed150-via-supper-club",
        "title": "Full day pool access for AED 150 + complimentary drink via Supper Club",
        "percentage": 30,
        "description": "Supper Club ME members get a full day pool pass at iKandy, Shangri-La Dubai for AED 150 — fully redeemable on F&B — plus a complimentary cocktail or wine.",
        "terms": "Booking through the Supper Club app required. AED 150 is fully redeemable on food & beverages.",
    },
    {
        "place_slug": "conrad-dubai-pool",
        "slug": "conrad-bogof-pool-via-supper-club",
        "title": "Buy 1 Get 1 Free pool day pass via Supper Club",
        "percentage": 50,
        "description": "Supper Club ME members get a buy-one-get-one-free pool day pass at Conrad Dubai. Effective 50% off when redeemed in pairs.",
        "terms": "Valid for Supper Club ME members. Subject to availability.",
    },
    {
        "place_slug": "jw-marriott-marquis-pool",
        "slug": "marquis-pool-fb-credit-via-supper-club",
        "title": "Full day pool access with F&B credit via Supper Club",
        "percentage": 30,
        "description": "Supper Club ME members get full-day pool access with food & beverage credit at the JW Marriott Marquis Dubai pool.",
        "terms": "F&B credit varies by package. Book through Supper Club for the current offer.",
    },
]


def add_supper_club_venues(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")

    place_by_slug = {}
    for spec in PLACES:
        place, _ = Place.objects.update_or_create(
            slug=spec["slug"],
            defaults={
                "name": spec["name"],
                "category": spec["category"],
                "area": spec["area"],
                "address": spec["address"],
                "website": spec["website"],
                "description": spec["description"],
                "is_published": True,
            },
        )
        place_by_slug[spec["slug"]] = place

    for spec in DISCOUNTS:
        place = place_by_slug[spec["place_slug"]]
        Discount.objects.update_or_create(
            slug=spec["slug"],
            defaults={
                "place": place,
                "title": spec["title"],
                "discount_type": "percentage",
                "percentage": spec["percentage"],
                "source_program": "supper_club",
                "description": spec["description"],
                "terms": spec["terms"],
                "is_active": True,
                "is_featured": False,
            },
        )


def remove_supper_club_venues(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")
    Discount.objects.filter(slug__in=[d["slug"] for d in DISCOUNTS]).delete()
    Place.objects.filter(slug__in=[p["slug"] for p in PLACES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0007_seed_programs"),
    ]

    operations = [
        migrations.RunPython(add_supper_club_venues, remove_supper_club_venues),
    ]
