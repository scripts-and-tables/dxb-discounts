"""Backfill `external_url` on Discount rows shipped before the field
existed. Sources we can deterministically link:

- Supper Club: each discount's slug is "supper-<sitemap-url-slug>",
  so the original booking URL is reconstructable.
- Caribou Fazaa, Caribou Perks, Mondoux Loyalty: hardcoded URLs.
- Caribou Esaad: no public per-merchant URL — left blank.

Depends on 0011_alter_external_url_max_length so the column is wide
enough to fit the longest known sitemap URL (217 chars).
"""
from django.db import migrations


HARDCODED = {
    "up-to-30-off-with-fazaa-card": "https://www.fazaa.ae/offers/view/caribou-coffee",
    "caribou-perks-earn-points-for-free-drinks": "https://www.cariboucoffee.com/caribou-perks/",
    "up-to-25-cashback-via-the-mondoux-app": "https://mondoux.ae/loyalty-program/",
}


def backfill(apps, schema_editor):
    Discount = apps.get_model("discounts", "Discount")

    # Supper Club: derive URL from slug.
    for d in Discount.objects.filter(source_program="supper_club", external_url=""):
        if not d.slug.startswith("supper-"):
            continue
        booking_slug = d.slug[len("supper-"):]
        d.external_url = f"https://supperclubme.com/product/booking/{booking_slug}"
        d.save(update_fields=["external_url"])

    # Hardcoded discounts (Caribou Fazaa, Caribou Perks, Mondoux Loyalty).
    for slug, url in HARDCODED.items():
        Discount.objects.filter(slug=slug, external_url="").update(external_url=url)


def clear_backfilled(apps, schema_editor):
    Discount = apps.get_model("discounts", "Discount")
    Discount.objects.filter(source_program="supper_club").update(external_url="")
    Discount.objects.filter(slug__in=list(HARDCODED.keys())).update(external_url="")


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0011_alter_external_url_max_length"),
    ]

    operations = [
        migrations.RunPython(backfill, clear_backfilled),
    ]
