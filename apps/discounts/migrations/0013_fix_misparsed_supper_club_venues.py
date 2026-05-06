"""Fix the six Supper Club Place rows whose names came out as the price
suffix (e.g. "AED99" instead of "Benjarong") because the original parser
split on the last " at " in the og:title, which sometimes pointed at a
"Starting at AED X" or "for only AED X" tail rather than the real venue.

For three of these the corrected slug already exists in the catalog
(another discount at the same venue parsed correctly), so we merge the
bad row's discounts onto the good row and delete the bad row. For the
other three the corrected slug is free, so we rename in place.

The parser has been tightened in scripts/parse_supperclub.py so future
imports won't repeat the mistake.
"""
from django.db import migrations


# (old_slug, new_slug, new_name, new_area)
FIXES = [
    ("aed99", "benjarong", "Benjarong", "Dusit Thani Dubai"),
    ("aed89", "the-lobby-lounge", "The Lobby Lounge", "Dusit Thani Dubai"),
    ("aed-75", "five-jumeirah-village-dubai", "FIVE Jumeirah Village Dubai", "Jumeirah Village"),
    ("aed160", "trattoria-by-cinque", "Trattoria by Cinque", "FIVE Jumeirah Village"),
    ("only-aed224", "dusit-thani", "Dusit Thani", "Dubai"),
    ("the-h-dubai-for-only-aed-65", "the-h-dubai", "The H Dubai", "Dubai"),
]


def fix_misparsed(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")

    for old_slug, new_slug, new_name, new_area in FIXES:
        bad = Place.objects.filter(slug=old_slug).first()
        if not bad:
            continue

        good = Place.objects.filter(slug=new_slug).exclude(id=bad.id).first()
        if good is not None:
            # Merge: move bad's discounts onto good, delete bad.
            Discount.objects.filter(place=bad).update(place=good)
            bad.delete()
        else:
            # Rename in place.
            bad.slug = new_slug
            bad.name = new_name
            bad.area = new_area
            bad.description = (
                f"{new_name} — {new_area}. Listed on Supper Club ME; booking "
                "and offer details available via supperclubme.com."
            )
            bad.save()


def revert_fixes(apps, schema_editor):
    """Rolling back this migration does NOT recreate the AED-as-name bug —
    that was always wrong. No-op."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0012_backfill_external_urls"),
    ]

    operations = [
        migrations.RunPython(fix_misparsed, revert_fixes),
    ]
