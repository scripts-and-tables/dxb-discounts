"""Seed the initial Experience tag set and auto-tag every existing Place
based on keywords found in any of its Discount titles.

Idempotent: experiences upsert on slug; auto-tagging only adds tags
that aren't already present.
"""
from django.db import migrations


EXPERIENCES = [
    ("breakfast",     "Breakfast",          10),
    ("brunch",        "Brunch",             20),
    ("lunch",         "Lunch",              30),
    ("dinner",        "Dinner",             40),
    ("afternoon-tea", "Afternoon tea",      50),
    ("drinks",        "Drinks & cocktails", 60),
    ("coffee",        "Coffee shop",        70),
    ("pool",          "Pool day",           80),
    ("beach",         "Beach day",          90),
    ("spa",           "Spa & wellness",    100),
    ("staycation",    "Hotel staycation",  110),
]

# Tag slug -> list of keyword phrases (lowercase). A place gets a tag if
# any of its discount titles contains one of these phrases.
KEYWORDS = {
    "breakfast":     ["breakfast"],
    "brunch":        ["brunch"],
    "lunch":         ["lunch", "business lunch"],
    "dinner":        ["dinner", "dinner buffet", "à la carte"],
    "afternoon-tea": ["afternoon tea", "high tea"],
    "drinks":        ["cocktail", "wine", "bubbly", "bar ", " bar,", "drinks"],
    "coffee":        ["coffee", "barista", "cafe ", "café "],
    "pool":          ["pool", "skypool", "pool club", "pool access"],
    "beach":         ["beach", "beach club"],
    "spa":           ["spa", "wellness", "massage", "facial"],
    "staycation":    ["staycation", "overnight", "hour stay", "hour staycation", "night stay"],
}


def seed_and_autotag(apps, schema_editor):
    Experience = apps.get_model("places", "Experience")
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")

    # Seed experiences.
    by_slug = {}
    for slug, label, sort_order in EXPERIENCES:
        exp, _ = Experience.objects.update_or_create(
            slug=slug,
            defaults={"label": label, "sort_order": sort_order, "is_active": True},
        )
        by_slug[slug] = exp

    # Auto-tag each place.
    for place in Place.objects.all().iterator():
        titles_blob = " ".join(
            Discount.objects.filter(place=place).values_list("title", flat=True)
        ).lower()
        # Also include the place's own name + description as evidence
        titles_blob += " " + (place.name or "").lower() + " " + (place.description or "").lower()
        if not titles_blob.strip():
            continue
        existing = set(place.experiences.values_list("slug", flat=True))
        for tag_slug, phrases in KEYWORDS.items():
            if tag_slug in existing:
                continue
            for phrase in phrases:
                if phrase in titles_blob:
                    place.experiences.add(by_slug[tag_slug])
                    break


def remove_seeded_experiences(apps, schema_editor):
    """Reverse: drop the experiences we seeded (cascades the M2M rows)."""
    Experience = apps.get_model("places", "Experience")
    Experience.objects.filter(slug__in=[s for s, _, _ in EXPERIENCES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("places", "0003_add_experience_and_place_experiences"),
        ("discounts", "0014_backfill_place_websites"),
    ]

    operations = [
        migrations.RunPython(seed_and_autotag, remove_seeded_experiences),
    ]
