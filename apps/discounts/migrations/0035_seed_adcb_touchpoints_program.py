"""Seed the ADCB TouchPoints Program row so it shows up in /discounts/.

Mirrors the pattern in 0029_seed_playbook_program.py — Program is a catalog
entry that the directory page enumerates. Discounts ingested by
`refresh-adcb-touchpoints` reference this Program via the
`DiscountProgram.ADCB_TOUCHPOINTS` choice on Discount.source_program.
"""
from django.db import migrations


ADCB_TOUCHPOINTS_PROGRAM = {
    "slug": "adcb_touchpoints",
    "name": "ADCB TouchPoints",
    "short_description": (
        "Abu Dhabi Commercial Bank's loyalty rewards programme for credit "
        "and debit cardholders — earn TouchPoints on spend, redeem at 2,000+ "
        "UAE partner outlets across travel, dining, retail, entertainment "
        "and bill payments."
    ),
    "description": (
        "TouchPoints is ADCB's award-winning loyalty programme. Every "
        "eligible card swipe earns TouchPoints (rate varies by card tier — "
        "up to 1.5 TPs per AED on the Infinite card). TouchPoints can be "
        "redeemed instantly at the till at participating retailers, used "
        "to pay phone/utility bills, converted to Emirates Skywards or "
        "Etihad Guest miles, or applied as cashback against statements.\n\n"
        "Separately, ADCB cardholders get access to a large catalogue of "
        "flat-percentage partner offers (dining, hotels, attractions, "
        "online retail) bookable directly with the card — this is the "
        "part dxb-discounts ingests via the refresh-adcb-touchpoints "
        "skill. Notable offers: VOX BOGO (up to 4 tickets/month), Talabat "
        "20% off, Noon 15% off on the Infinite card."
    ),
    "official_url": "https://www.adcb.com/en/personal/cards/credit-cards/",
    "cost_summary": "Free with any ADCB credit/debit card",
    "eligibility": "ADCB credit or debit cardholders (UAE residents)",
    "sort_order": 130,
    "tiers": [
        {"name": "Platinum card",
         "threshold": "Eligible spend on an ADCB Platinum-tier card",
         "benefit": "Up to 1 TouchPoint per AED + 10,000 bonus TPs on AED 10k monthly spend"},
        {"name": "Infinite card",
         "threshold": "Eligible spend on an ADCB Infinite-tier card",
         "benefit": "Up to 1.5 TouchPoints per AED + VOX BOGO, Talabat 20%, Noon 15%"},
    ],
    "expected_savings": (
        "Heavy card users typically redeem AED 1,500–5,000/year in "
        "partner discounts and statement credits. Top tiers benefit "
        "considerably more from the flat-percentage partner catalogue "
        "than from the points-earning mechanic on its own."
    ),
}


def seed(apps, schema_editor):
    Program = apps.get_model("discounts", "Program")
    Program.objects.update_or_create(
        slug=ADCB_TOUCHPOINTS_PROGRAM["slug"],
        defaults={k: v for k, v in ADCB_TOUCHPOINTS_PROGRAM.items() if k != "slug"},
    )


def reverse(apps, schema_editor):
    Program = apps.get_model("discounts", "Program")
    Program.objects.filter(slug=ADCB_TOUCHPOINTS_PROGRAM["slug"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0034_alter_discount_source_program"),
    ]

    operations = [
        migrations.RunPython(seed, reverse),
    ]
