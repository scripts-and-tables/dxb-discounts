"""Seed ~25 curated Zomato Gold venues in Dubai.

Zomato Gold (relaunched in UAE in 2024 under the "District by Zomato"
umbrella) gives members Buy 1 Get 1 on food and 2-for-2 on drinks at
4,000+ UAE restaurants. The mechanic is uniform across all partners,
so we only need the participating venue list — there's no per-venue
discount data to parse.

This seed is **option A from the user's decision tree**: a hand-curated
list of recognisable Dubai Gold partners. The Zomato search API is
fully XHR-loaded and pagination doesn't work via URL — full programmatic
ingest would require reverse-engineering the XHR API or using a headless
browser. Both are deferred. The venues here are sourced from:

  - the live Zomato `?gold_partner=1` filtered page (~9 visible without
    JS rendering)
  - Zomato's own marketing copy (blog, press releases)
  - HSBC / Mastercard partnership announcements that list named partners

Migration is idempotent: get_or_create on Place by slug, update_or_create
on Discount by `zomato-gold-{place-slug}` slug. Re-applying is a no-op.
"""
from django.db import migrations
from django.utils.text import slugify


# (name, area, zomato_url_slug, category)
# category is one of: restaurant, hotel, retail, attraction, service
VENUES = [
    # Visible on zomato.com/dubai/restaurants?gold_partner=1 (SSR-rendered)
    ("Applebee's",                 "Dubai Festival City",      "applebees-1-dubai-festival-city",                                  "restaurant"),
    ("Azure Pool Bar",             "Jumeirah Beach Residence", "azure-pool-bar-sheraton-jumeirah-beach-resort-jumeirah-beach-residence", "restaurant"),
    ("Channels",                   "Barsha Heights",           "channels-radisson-blu-barsha-heights-barsha-heights",              "restaurant"),
    ("Cilantro",                   "Dubai Media City",         "cilantro-arjaan-by-rotana-dubai-media-city",                       "restaurant"),
    ("DXBlends",                   "Umm Hurair",               "dxblends-umm-hurair",                                              "restaurant"),
    ("IHOP",                       "Dubai Festival City",      "ihop-dubai-festival-city",                                         "restaurant"),
    ("Pawar Family Restaurant",    "International City",       "pawar-family-restaurant-international-city",                       "restaurant"),
    ("Ramzin Cafe",                "Hor Al Anz",               "ramzin-cafe-1-hor-al-anz",                                         "restaurant"),
    ("WOFL",                       "Jumeirah Beach Residence", "wofl-jumeirah-beach-residence",                                    "restaurant"),

    # Mentioned in Zomato's own marketing copy / blog as Gold Food/Drink Partners
    ("Kaftan Turkish Cuisine & Fine Art", "Business Bay",      "kaftan-turkish-cuisine-fine-art-business-bay",                     "restaurant"),
    ("Wakame",                     "Downtown Dubai",           "wakame-sofitel-dubai-downtown",                                    "restaurant"),
    ("Intersect by Lexus",         "DIFC",                     "intersect-by-lexus-difc",                                          "restaurant"),
    ("Gaucho",                     "DIFC",                     "gaucho-difc",                                                      "restaurant"),
    ("Leopold's of London",        "Downtown Dubai",           "leopolds-of-london-downtown-dubai",                                "restaurant"),
    ("Art House Cafe",             "Jumeirah",                 "art-house-cafe-jumeirah",                                          "restaurant"),
    ("Bubo Barcelona Cafe",        "Downtown Dubai",           "bubo-barcelona-cafe-downtown-dubai",                               "restaurant"),
    ("Cafe Mandarina",             "Downtown Dubai",           "cafe-mandarina-downtown-dubai",                                    "restaurant"),
    ("Crumbs Elysee",              "Downtown Dubai",           "crumbs-elysee-downtown-dubai",                                     "restaurant"),
    ("Treej Cafe",                 "Dubai Hills",              "treej-cafe-dubai-hills",                                           "restaurant"),
    ("Mitts & Trays",              "Jumeirah",                 "mitts-trays-jumeirah",                                             "restaurant"),

    # Zomato 2025 "Tastemakers" award winners (well-known Dubai destinations)
    ("Al Sultan Restaurant & Grill", "Deira",                  "al-sultan-restaurant-and-grill-deira",                             "restaurant"),
    ("Five Guys",                  "Dubai Mall",               "five-guys-the-dubai-mall-downtown-dubai",                          "restaurant"),
    ("Pizza Di Rocco",             "Jumeirah Lake Towers",     "pizza-di-rocco-jumeirah-lake-towers",                              "restaurant"),
    ("At.mosphere",                "Downtown Dubai",           "atmosphere-burj-khalifa-downtown-dubai",                           "restaurant"),
    ("Trèsind",                    "Sheikh Zayed Road",        "tresind-nassima-royal-hotel-sheikh-zayed-road",                    "restaurant"),
]

ZOMATO_DESCRIPTION = (
    "Zomato Gold members get Buy 1 Get 1 free on food and 2-for-2 on "
    "drinks at participating Dubai restaurants — typically a 50% saving on "
    "the bill before even ordering a brunch. Annual membership is ~AED 149 "
    "and is currently free for HSBC, FAB and Mastercard cardholders via "
    "their respective partner programmes. Sign up via the Zomato app."
)

ZOMATO_TERMS = (
    "Must be an active Zomato Gold member; verify the venue's Gold partner "
    "status in the app before ordering as participation rotates monthly. "
    "Maximum redemption: 1 complimentary dish per Gold member at the table "
    "for food, 2 complimentary drinks at drink partners. Excludes alcohol "
    "at most venues. Not combinable with other discounts (Entertainer, "
    "Fazaa, etc.) at the same bill. Full T&Cs at zomato.com/dubai/gold."
)


def seed_zomato_gold(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")

    for name, area, zomato_slug, category in VENUES:
        place_slug = slugify(name)[:200] or "place"
        # If a Place already exists with this slug, reuse it (avoids creating
        # a parallel row when Entertainer/Fazaa already seeded the brand).
        place, _ = Place.objects.get_or_create(
            slug=place_slug,
            defaults={
                "name": name,
                "category": category,
                "area": area,
                "is_published": True,
            },
        )
        # Backfill empty fields when the Place pre-existed
        updates = {}
        if not place.area and area:
            updates["area"] = area
        if updates:
            for k, v in updates.items():
                setattr(place, k, v)
            place.save()

        Discount.objects.update_or_create(
            slug=f"zomato-gold-{place_slug}",
            defaults={
                "place": place,
                "title": f"{name} — Buy 1 Get 1 with Zomato Gold",
                "discount_type": "bogo",
                "source_program": "zomato",
                "description": ZOMATO_DESCRIPTION,
                "terms": ZOMATO_TERMS,
                "external_url": f"https://www.zomato.com/dubai/{zomato_slug}",
                "is_members_only": True,
                "is_active": True,
            },
        )


def remove_zomato_gold(apps, schema_editor):
    Discount = apps.get_model("discounts", "Discount")
    Discount.objects.filter(slug__startswith="zomato-gold-").delete()
    # Don't delete the Places — they may have other discounts (Entertainer,
    # Fazaa) attached from prior ingests. Removing the Discount is enough
    # to undo this migration.


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0035_seed_adcb_touchpoints_program"),
        ("places", "0018_rerun_dedup_with_relaxed_rules"),
    ]

    operations = [
        migrations.RunPython(seed_zomato_gold, remove_zomato_gold),
    ]
