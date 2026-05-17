"""Disambiguate the two The Hamptons Cafe outlets in the home page.

After 0037 seeded both Hamptons Cafe branches (Emirates Hills + Umm
Suqeim), they appeared as two visually-identical "The Hamptons Cafe"
cards on the home page — confusing UX, looks like a duplication bug.

The dedup-places skill correctly DOESN'T merge these (per its own logic
they're legitimate distinct branches: same brand, different areas,
same source program). The actual fix is to make the branch labels
visible. Other multi-outlet brands in the catalogue follow the
"{brand} — {outlet}" naming convention (e.g. Entertainer ingest uses
`_entertainer_place_name`). Mirror that here.
"""
from django.db import migrations


RENAMES = [
    ("the-hamptons-cafe-emirates-hills", "The Hamptons Cafe — Emirates Hills"),
    ("the-hamptons-cafe-umm-suqeim",     "The Hamptons Cafe — Umm Suqeim"),
]


def rename_forward(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    for slug, new_name in RENAMES:
        Place.objects.filter(slug=slug).update(name=new_name)


def rename_back(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    for slug, _ in RENAMES:
        Place.objects.filter(slug=slug).update(name="The Hamptons Cafe")


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0038_zomato_visible_to_anon"),
        ("places", "0018_rerun_dedup_with_relaxed_rules"),
    ]

    operations = [
        migrations.RunPython(rename_forward, rename_back),
    ]
