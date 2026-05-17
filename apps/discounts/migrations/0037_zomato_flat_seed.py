"""Seed 49 verified Zomato flat-% discounts.

A follow-up to 0036_zomato_gold_seed.py. The first seed only captured
Zomato Gold venues with the BOGO (Buy-1-Get-1) mechanic. After probing
Zomato pages we discovered that many venues actually publish a
**flat-percentage instant offer** (offerType="dining_gold" with a
"No booking required" subtitle and a concrete percentage between 10%
and 30%) — distinct from the BOGO mechanic and from the pre-book
dineout discount.

These 49 venues were verified by `scripts/probe_zomato_offers.py`:
candidates pulled from Zomato's SSR-rendered locality pages (which
ship valid slugs), each page fetched, `SECTION_DINING_OFFERS_V2`
parsed, and only the "INSTANT OFFER" flat-% entries kept. The
discount percentage in this migration is the value Zomato displayed
at probe time.

Migration is idempotent: get_or_create on Place by slug,
update_or_create on Discount by `zomato-flat-{place-slug}`.
"""
from django.db import migrations


# (display_name, area, place_slug, zomato_url_slug, percentage)
# Slugs are deduplicated against in-migration collisions (multiple
# branches of Applebee's, Buffalo Wings & Rings, The Hamptons Cafe).
# Existing brand Places from Entertainer / Fazaa with different slugs
# may show up as parallel rows — dedup-places skill cleans those up.
VENUES = [
    ("Al Amoor Express",               "Trade Centre Area",        "al-amoor-express",                              "al-amoor-express-trade-centre-area", 15),
    ("Allo Beirut",                    "Al Safa",                  "allo-beirut",                                   "allo-beirut-al-safa", 15),
    ("Applebee's",                     "Al Barsha",                "applebees-al-barsha",                           "applebees-al-barsha", 10),
    ("Applebee's",                     "Dubai Festival City",      "applebees-dubai-festival-city",                 "applebees-1-dubai-festival-city", 10),
    ("Arabeska Elite Restaurant",      "Downtown Dubai",           "arabeska-elite-restaurant",                     "arabeska-elite-restaurant-downtown-dubai", 15),
    ("Azad Hind",                      "Jumeirah Lake Towers",     "azad-hind",                                     "azad-hind-jumeirah-lake-towers", 10),
    ("Azure Pool Bar (Sheraton JBR)",  "Jumeirah Beach Residence", "azure-pool-bar-sheraton-jbr",                   "azure-pool-bar-sheraton-jumeirah-beach-resort-jumeirah-beach-residence", 25),
    ("B-Town Restro Bar",              "Al Barsha",                "b-town-restro-bar",                             "b-town-restro-bar-al-barsha", 15),
    ("Barbecue Delights",              "Jumeirah Beach Residence", "barbecue-delights",                             "barbecue-delights-jumeirah-beach-residence", 20),
    ("BB Social Dining",               "DIFC",                     "bb-social-dining",                              "bb-social-dining-difc", 15),
    ("Beirut Khanum",                  "Downtown Dubai",           "beirut-khanum",                                 "beirut-khanum-downtown-dubai", 25),
    ("Beresta",                        "Business Bay",             "beresta",                                       "beresta-1-business-bay", 10),
    ("Biryani By Kilo",                "Al Barsha",                "biryani-by-kilo",                               "biryani-by-kilo-al-barsha", 10),
    ("Buffalo Wings & Rings",          "DIFC",                     "buffalo-wings-rings-difc",                      "buffalo-wings-rings-difc", 15),
    ("Buffalo Wings & Rings",          "Jumeirah Lake Towers",     "buffalo-wings-rings-jumeirah-lake-towers",      "buffalo-wings-rings-jumeirah-lake-towers", 15),
    ("Chai Wala Cafe",                 "Al Quoz",                  "chai-wala-cafe",                                "chai-wala-cafe-al-quoz", 10),
    ("Channels (Radisson Blu)",        "Barsha Heights",           "channels-radisson-blu",                         "channels-radisson-blu-barsha-heights-barsha-heights", 15),
    ("Chicken Tikka Inn",              "Al Barsha",                "chicken-tikka-inn",                             "chicken-tikka-inn-1-al-barsha", 15),
    ("Cilantro (Arjaan by Rotana)",    "Dubai Media City",         "cilantro-arjaan-by-rotana",                     "cilantro-arjaan-by-rotana-dubai-media-city", 15),
    ("Coco Grill Lounge",              "Downtown Dubai",           "coco-grill-lounge",                             "coco-grill-lounge-downtown-dubai", 10),
    ("Culinary Park Restaurant",       "Al Barsha",                "culinary-park-restaurant",                      "culinary-park-restaurant-al-barsha", 15),
    ("Dishtrict",                      "Jumeirah 1",               "dishtrict",                                     "dishtrict-jumeirah-1", 20),
    ("DXBlends",                       "Umm Hurair",               "dxblends",                                      "dxblends-umm-hurair", 10),
    ("Gazebo",                         "Jumeirah 1",               "gazebo",                                        "gazebo-jumeirah-1", 10),
    ("Gwalia",                         "Jumeirah Lake Towers",     "gwalia",                                        "gwalia-jumeirah-lake-towers", 10),
    ("IHOP",                           "Dubai Festival City",      "ihop",                                          "ihop-dubai-festival-city", 10),
    ("Indian Food Company Restaurant", "Jumeirah Lake Towers",     "indian-food-company-restaurant",                "indian-food-company-restaurant-jumeirah-lake-towers", 20),
    ("Iyer's Premium Veg Restaurant",  "Jumeirah Lake Towers",     "iyers-premium-veg-restaurant",                  "iyers-premium-veg-restaurant-jumeirah-lake-towers", 10),
    ("Keto Cafe by GBF",               "Downtown Dubai",           "keto-cafe-by-gbf",                              "keto-cafe-by-gbf-downtown-dubai", 20),
    ("Khau Galli",                     "Jumeirah Lake Towers",     "khau-galli",                                    "khau-galli-jumeirah-lake-towers", 20),
    ("Koreana",                        "Al Barsha",                "koreana",                                       "koreana-al-barsha", 30),
    ("Korma Sutra Restaurant & Cafe",  "Al Barsha",                "korma-sutra-restaurant-cafe",                   "korma-sutra-restaurant-cafe-al-barsha", 15),
    ("La Fabbrica Focacceria Italiana","Jumeirah 1",               "la-fabbrica-focacceria-italiana",               "la-fabbrica-focacceria-italiana-jumeirah-1", 10),
    ("Melt & More",                    "Dubai Hills",              "melt-more",                                     "melt-more-dubai-hills", 25),
    ("Moshi Momo Sushi",               "Jumeirah Lake Towers",     "moshi-momo-sushi",                              "moshi-momo-sushi-jumeirah-lake-towers", 10),
    ("Nawab",                          "Jebel Ali Village",        "nawab",                                         "nawab-jebel-ali-village", 10),
    ("Nine Squares Restaurant",        "Umm Suqeim",               "nine-squares-restaurant",                       "nine-squares-restaurant-umm-suqeim", 10),
    ("Patiala",                        "Downtown Dubai",           "patiala",                                       "patiala-downtown-dubai", 30),
    ("Pawar Family Restaurant",        "International City",       "pawar-family-restaurant",                       "pawar-family-restaurant-international-city", 10),
    ("Pincode by Kunal Kapur",         "Dubai Hills",              "pincode-by-kunal-kapur",                        "pincode-by-kunal-kapur-dubai-hills", 10),
    ("Ramzin Cafe",                    "Hor Al Anz",               "ramzin-cafe",                                   "ramzin-cafe-1-hor-al-anz", 15),
    ("Sips N Taps",                    "Al Satwa",                 "sips-n-taps",                                   "sips-n-taps-al-satwa", 30),
    ("Slay Bar and Kitchen",           "DIFC",                     "slay-bar-and-kitchen",                          "slay-bar-and-kitchen-difc", 15),
    ("The Big Chill Cafe",             "Dubai Hills",              "the-big-chill-cafe",                            "the-big-chill-cafe-dubai-hills", 10),
    ("The Hamptons Cafe",              "Emirates Hills",           "the-hamptons-cafe-emirates-hills",              "the-hamptons-cafe-emirates-hills", 10),
    ("The Hamptons Cafe",              "Umm Suqeim",               "the-hamptons-cafe-umm-suqeim",                  "the-hamptons-cafe-umm-suqeim", 10),
    ("WOFL",                           "Jumeirah Beach Residence", "wofl",                                          "wofl-jumeirah-beach-residence", 10),
    ("Wok of Fame",                    "Business Bay",             "wok-of-fame",                                   "wok-of-fame-business-bay", 20),
    ("Yoko Sizzlers",                  "Al Barsha",                "yoko-sizzlers",                                 "yoko-sizzlers-al-barsha", 10),
]

ZOMATO_FLAT_DESCRIPTION = (
    "Zomato Gold members get a flat percentage off the food bill at "
    "this restaurant — no booking required, no minimum spend. Just "
    "show your Zomato Gold membership before paying. Annual Gold "
    "membership is ~AED 149 (often free for HSBC, FAB and Mastercard "
    "cardholders). Sign up via the Zomato app."
)

ZOMATO_FLAT_TERMS = (
    "Must be an active Zomato Gold member; verify the venue's current "
    "Gold partner status in the Zomato app — Zomato rotates partner "
    "lists and percentages periodically. Discount typically applies to "
    "the food bill, often excluding alcohol and service charge. Not "
    "combinable with other discounts (Entertainer, Fazaa, etc.) at the "
    "same bill. Full T&Cs at zomato.com/dubai/gold."
)


def seed_zomato_flat(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")

    for name, area, place_slug, zomato_slug, pct in VENUES:
        place, _ = Place.objects.get_or_create(
            slug=place_slug,
            defaults={
                "name": name,
                "category": "restaurant",
                "area": area,
                "is_published": True,
            },
        )
        # Backfill empty area if the Place pre-existed without one
        if not place.area and area:
            place.area = area
            place.save(update_fields=["area"])

        Discount.objects.update_or_create(
            slug=f"zomato-flat-{place_slug}",
            defaults={
                "place": place,
                "title": f"{name} — Flat {pct}% off with Zomato Gold",
                "discount_type": "percentage",
                "percentage": pct,
                "source_program": "zomato",
                "description": ZOMATO_FLAT_DESCRIPTION,
                "terms": ZOMATO_FLAT_TERMS,
                "external_url": f"https://www.zomato.com/dubai/{zomato_slug}",
                "is_members_only": True,
                "is_active": True,
            },
        )


def remove_zomato_flat(apps, schema_editor):
    Discount = apps.get_model("discounts", "Discount")
    Discount.objects.filter(slug__startswith="zomato-flat-").delete()
    # Leave Places intact — they may have offers from other source programs.


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0036_zomato_gold_seed"),
        ("places", "0018_rerun_dedup_with_relaxed_rules"),
    ]

    operations = [
        migrations.RunPython(seed_zomato_flat, remove_zomato_flat),
    ]
