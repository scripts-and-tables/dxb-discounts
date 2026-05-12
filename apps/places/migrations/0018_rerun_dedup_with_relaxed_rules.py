"""One-shot: re-run audit+merge with the relaxed dedup rules.

Two key rule changes that warrant a fresh pass on prod:

1. 2-token brand prefixes now allow `{entertainer, fazaa}` mixed-source
   branches (previously rejected mixes were entertainer+fazaa). E.g.
   "Adventure Island - CCD" (entertainer+fazaa) + "Adventure Island -
   JBR" (entertainer-only) now auto-merge into one synthesized brand.

2. The synthesizable bucket-by-1-token logic now falls back to
   sub-bucketing by 2-token when the broader bucket is heterogeneous.
   Previously a 9-member "adventure" bucket would collapse all
   adventure-prefix Places into one bogus synthesized brand; now
   genuine 2-member sub-clusters (e.g. "adventure island") surface
   independently while singletons (Adventure Park, Adventure Tours,
   etc.) are left alone.

Also removed ambiguous words ("island", "park", "village", "beach")
from the LOCATION_SUFFIX_WORDS trim list because they're frequently
part of brand names (Adventure Island, Adventure Park).

Idempotent — no-op if there's nothing left to merge.
"""
from django.core.management import call_command
from django.db import migrations


def consolidate(apps, schema_editor):
    from scripts.audit_place_duplicates import audit
    for pass_num in range(1, 4):
        print(f"\n=== consolidate pass {pass_num} (relaxed rules) ===")
        n = audit()
        if n == 0:
            print(f"  no clusters; stopping after pass {pass_num - 1}.")
            break
        call_command("merge_places", apply=True)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("places", "0017_clear_entertainer_boilerplate_descriptions"),
    ]

    operations = [
        migrations.RunPython(consolidate, noop_reverse),
    ]
