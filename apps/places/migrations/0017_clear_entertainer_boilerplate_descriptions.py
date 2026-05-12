"""One-shot: clear the boilerplate Entertainer description from Places.

Migrations 0015-0017 in apps/discounts/ seeded ~778 Places with a
generic description template like:

  "{name} - Dubai outlet listed on The Entertainer. Buy-one-get-one-free
   offers; details on theentertainerme.com."

After per-offer ingest landed and we synthesized brand-level Places,
this boilerplate became misleading — it talks about a specific outlet,
not the brand row, and reads like an ad copy. The user wants Places
to carry only real, curated descriptions; the boilerplate should go.

Leaves any non-boilerplate description alone (curator data is sacred).
"""
from django.db import migrations


_BOILERPLATE_FRAGMENT = "listed on The Entertainer"


def clear_descriptions(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    qs = Place.objects.filter(description__contains=_BOILERPLATE_FRAGMENT)
    n = qs.count()
    qs.update(description="")
    print(f"[0017_clear_entertainer_boilerplate] cleared description on {n} Places.")


def noop_reverse(apps, schema_editor):
    """We can't reconstruct the per-place boilerplate text. Leave as-is."""
    return


class Migration(migrations.Migration):

    dependencies = [
        ("places", "0016_rerun_dedup_and_rename"),
    ]

    operations = [
        migrations.RunPython(clear_descriptions, noop_reverse),
    ]
