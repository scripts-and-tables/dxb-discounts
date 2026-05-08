"""Seed Atlantis Circle (loyalty program for Atlantis Dubai resorts) with
the 20 Dubai dining venues that accept Circle members for tiered F&B
discounts.

Atlantis Circle tiers (already seeded on the Program row in 0020):
  Blue   (free signup)   — 15% off F&B
  Silver (AED 12k/year)  — 20% off
  Gold   (AED 25k/year)  — 25% off
  Black  (AED 40k/year)  — 30% off

The Discount.percentage stored on each row uses 15 (Blue baseline) — the
discount everyone gets for free signup. The description explains the
tiered upgrade.

Some venues were on temporary operational pause in April 2026 (Hakkasan,
Ossiano, Dinner by Heston, Ling Ling, La Mar, Cloud 22) per The National.
They're included here since the Circle program covers them when they
reopen, and the Atlantis Dubai resort positions them as core dining.

Idempotent: get_or_create on slug, update_or_create on Discount.
"""
from django.db import migrations


# Atlantis The Palm + Atlantis The Royal both sit on Crescent Road, Palm Jumeirah.
PALM_ADDRESS = "Atlantis The Palm, Crescent Road, Palm Jumeirah, Dubai"
ROYAL_ADDRESS = "Atlantis The Royal, Crescent Road, Palm Jumeirah, Dubai"

# (slug, name, atlantis_url_segment, resort, cuisine_blurb)
VENUES = [
    # Atlantis The Palm
    ("hakkasan-atlantis-the-palm", "Hakkasan",
     "hakkasan", "palm",
     "MICHELIN-starred Cantonese restaurant at Atlantis, The Palm — premium dim sum, stir-fries and signature cocktails by Chef Andy Toh."),
    ("ossiano",                    "Ossiano",
     "ossiano", "palm",
     "Dubai's one-MICHELIN-star underwater fine-dining restaurant at Atlantis, The Palm — degustation menu with floor-to-ceiling aquarium views."),
    ("saffron-atlantis",           "Saffron",
     "saffron", "palm",
     "Pan-Asian buffet at Atlantis, The Palm with 220 dishes across 20+ live cooking stations — dim sum, stir-fries, curries, sushi."),
    ("kaleidoscope",               "Kaleidoscope",
     "kaleidoscope", "palm",
     "International buffet at Atlantis, The Palm with Arabic, Asian and continental specialties across multiple live stations."),
    ("wavehouse",                  "Wavehouse",
     "wavehouse", "palm",
     "Family casual at Atlantis, The Palm — bowling, arcade games, and a menu of burgers, pizzas, wings and shakes."),
    ("gordon-ramsay-bread-street-kitchen", "Gordon Ramsay Bread Street Kitchen",
     "gordon-ramsay-bread-street-kitchen", "palm",
     "Modern British by Gordon Ramsay at Atlantis, The Palm — classic dishes, Sunday roast, lively bar."),
    ("street-pizza-atlantis",      "Gordon Ramsay's Street Pizza",
     "street-pizza", "palm",
     "Endless pizza slices and drinks shaped by Gordon Ramsay's crowd-favourite flavours — at Atlantis, The Palm."),
    ("ayamna",                     "Ayamna",
     "ayamna", "palm",
     "Lebanese restaurant at Atlantis, The Palm — warm mezze, chargrilled meats and seafood, time-honoured desserts."),
    ("seafire-steakhouse",         "Seafire Steakhouse",
     "seafire-steakhouse", "palm",
     "New York-style steakhouse at Atlantis, The Palm — premium cuts, seafood and a curated wine list."),
    ("en-fuego",                   "En Fuego",
     "en-fuego", "palm",
     "Latin American restaurant at Atlantis, The Palm — Mexican classics, fajitas, margaritas and a vibrant bar."),

    # Atlantis The Royal
    ("dinner-by-heston-blumenthal", "Dinner by Heston Blumenthal",
     "dinner-by-heston", "royal",
     "MICHELIN-starred contemporary British by Heston Blumenthal at Atlantis The Royal — historic British recipes reimagined (Meat Fruit, Tipsy Cake)."),
    ("estiatorio-milos",           "Estiatorio Milos",
     "milos", "royal",
     "Authentic Greek seafood at Atlantis The Royal — fresh oysters, ceviches, tzatziki, with views over the resort fountains."),
    ("cloud22",                    "Cloud 22",
     "cloud22", "royal",
     "Rooftop infinity-pool day club and bar at Atlantis The Royal — handcrafted cocktails and small plates 22 floors up."),
    ("the-royal-tearoom",          "The Royal Tearoom",
     "the-royal-tearoom", "royal",
     "Lavish afternoon tea at Atlantis The Royal — curated pastries, sweet and savoury bites, premium teas."),
    ("arianas-persian-kitchen",    "Ariana's Persian Kitchen",
     "arianas-kitchen", "royal",
     "Modern Persian cuisine at Atlantis The Royal — saffron rice, kebabs, slow-cooked stews and traditional desserts."),
    ("jaleo-by-jose-andres",       "Jaleo by José Andrés",
     "jaleo", "royal",
     "Spanish tapas by Chef José Andrés at Atlantis The Royal — paella, sangria, jamón ibérico and an extensive Spanish wine list."),
    ("ling-ling-atlantis",         "Ling Ling",
     "ling-ling", "royal",
     "Pan-Asian dining and lounge at Atlantis The Royal — Japanese, Thai, Vietnamese and Korean dishes with DJ-driven evenings."),
    ("nobu-by-the-beach",          "Nobu by The Beach",
     "nobu-by-the-beach", "royal",
     "Beachfront Nobu (Japanese-Peruvian) at Atlantis The Royal — private cabanas, signature black cod miso, sushi and cocktails."),
    ("gastronomy-atlantis",        "Gastronomy",
     "gastronomy", "royal",
     "Breakfast and dinner buffet at Atlantis The Royal — global cuisine with live cooking and premium ingredients."),
    ("la-mar-by-gaston-acurio",    "La Mar by Gastón Acurio",
     "la-mar", "royal",
     "Peruvian seafood by Chef Gastón Acurio at Atlantis The Royal — ceviche, tiradito, anticucho, Novo-Andean specials."),
]


def add_atlantis_circle(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")

    for slug, name, url_seg, resort, blurb in VENUES:
        address = ROYAL_ADDRESS if resort == "royal" else PALM_ADDRESS
        place, _ = Place.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "category": "restaurant",
                "area": "Palm Jumeirah",
                "address": address,
                "phone": "",
                "website": f"https://www.atlantis.com/dubai/dining/{url_seg}",
                "description": blurb,
                "is_published": True,
            },
        )
        # Even if the Place pre-existed, fill in any blank fields that we
        # can authoritatively populate from this curated source.
        updates = {}
        if not place.address:
            updates["address"] = address
        if not place.website:
            updates["website"] = f"https://www.atlantis.com/dubai/dining/{url_seg}"
        if not place.description:
            updates["description"] = blurb
        if updates:
            for k, v in updates.items():
                setattr(place, k, v)
            place.save()

        Discount.objects.update_or_create(
            slug=f"atlantis-circle-{slug}",
            defaults={
                "place": place,
                "title": f"{name} — 15% off with Atlantis Circle (Blue, free)",
                "discount_type": "percentage",
                "percentage": 15,
                "source_program": "atlantis_circle",
                "description": (
                    f"{blurb}\n\n"
                    f"Atlantis Circle members get tiered F&B discounts at all Atlantis "
                    f"Dubai dining venues. The free Blue tier earns 15% off; the discount "
                    f"scales with annual dining spend (Silver 20%, Gold 25%, Black 30%). "
                    f"Sign up free at https://www.atlantis.com/dubai/membership/atlantis-circle."
                ),
                "terms": (
                    "Discount applies to the food & beverage bill, excluding alcohol "
                    "and service charge unless stated. Members must present a valid "
                    "Atlantis Circle digital card before settling. Tier % is set by "
                    "rolling 12-month dining spend at Atlantis Dubai venues. See "
                    "atlantis.com/dubai/membership/atlantis-circle for full terms, "
                    "exclusions and tier qualifying rules."
                ),
                "external_url": f"https://www.atlantis.com/dubai/dining/{url_seg}",
                "is_active": True,
                "is_featured": False,
            },
        )


def remove_atlantis_circle(apps, schema_editor):
    Discount = apps.get_model("discounts", "Discount")
    Place = apps.get_model("places", "Place")
    Discount.objects.filter(slug__startswith="atlantis-circle-").delete()
    Place.objects.filter(slug__in=[v[0] for v in VENUES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0025_refresh_fazaa_from_api"),
        ("places", "0004_seed_experiences_and_autotag"),
    ]

    operations = [
        migrations.RunPython(add_atlantis_circle, remove_atlantis_circle),
    ]
