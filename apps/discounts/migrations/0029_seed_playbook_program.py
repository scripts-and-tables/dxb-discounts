"""Seed the Playbook Program row so it shows up in the /discounts/ directory.

Mirrors the pattern in 0020_seed_new_programs_and_tiers.py — Program is a
catalog entry that the directory page enumerates. Without this row, Playbook
Discount tiles would render but the program itself wouldn't appear in the
list of programs at /discounts/.
"""
from django.db import migrations


PLAYBOOK_PROGRAM = {
    "slug": "playbook",
    "name": "Playbook",
    "short_description": (
        "Free F&B discovery app for Dubai/Abu Dhabi — set menus, brunches, "
        "ladies nights, business lunches and happy hours across 1,400+ "
        "restaurants and bars. No subscription, no membership card."
    ),
    "description": (
        "Playbook is a free lifestyle app from the team behind Repeat (now "
        "discontinued). It aggregates curated F&B offers across the UAE — "
        "set menus, brunches, ladies nights, business lunches, happy hours, "
        "afternoon tea — into one searchable directory with maps, photos and "
        "filters. Each venue typically lists 3-6 named deals (e.g. \"Business "
        "Lunch\", \"Ladies Night\", \"Day Brunch\") with the price, time "
        "window and any conditions written out in plain English.\n\n"
        "There's no card and no subscription — you just open the app, find "
        "an offer, and either book through the in-app reservation link or "
        "walk in and mention the deal. Available on iOS and Android, plus "
        "the my-playbook.com website."
    ),
    "official_url": "https://www.my-playbook.com",
    "cost_summary": "Free",
    "eligibility": "Anyone — no card or signup required",
    "sort_order": 60,
    "tiers": [
        {"name": "Free user", "threshold": "Download the app",
         "benefit": "Access to every curated offer across 1,400+ Dubai venues; book via in-app link or walk in"},
    ],
    "expected_savings": (
        "Set menus and brunches typically save 30–50% off à la carte; ladies "
        "nights and happy hours are essentially free drinks for 2-3 hours. "
        "Active diners save AED 1,000–3,000+ per year vs ordering at full price."
    ),
}


def seed(apps, schema_editor):
    Program = apps.get_model("discounts", "Program")
    Program.objects.update_or_create(
        slug=PLAYBOOK_PROGRAM["slug"],
        defaults={k: v for k, v in PLAYBOOK_PROGRAM.items() if k != "slug"},
    )


def reverse(apps, schema_editor):
    Program = apps.get_model("discounts", "Program")
    Program.objects.filter(slug=PLAYBOOK_PROGRAM["slug"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0028_alter_discount_source_program"),
    ]

    operations = [
        migrations.RunPython(seed, reverse),
    ]
