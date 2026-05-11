"""One-shot: merge cross-source duplicate Places on production.

Runs the merge_places management command (which reads
data/place_duplicates_enriched.json) against prod. The JSON was
generated locally by scripts/audit_place_duplicates.py — see the
dedup-places skill for the cascade rules.

What this does on prod (matches the local apply log):
- 11 high-confidence pairs auto-merge
- ~21 Discount.place_id rows re-pointed to the canonical
- 11 Place rows soft-deleted (is_published=False), kept in DB so old
  admin links still work
- Empty canonical fields (website, address, phone, lat/lng, etc.)
  get backfilled from the loser; non-empty fields are never overwritten

Idempotent: re-running finds 0 eligible clusters because losers are
already is_published=False and the auditor only considers
is_published=True rows.

Following the pattern in 0009 / 0011 / 0012: commit the data file with
this migration; revert in a follow-up commit once prod has applied.
"""
from django.core.management import call_command
from django.db import migrations


def merge_duplicates(apps, schema_editor):
    call_command("merge_places", apply=True)


def noop_reverse(apps, schema_editor):
    """Leaves the DB as-is. We don't want to silently un-soft-delete
    losers or move discounts back on rollback — manual cleanup if needed."""
    return


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("places", "0012_ingest_fazaa_playbook_production"),
    ]

    operations = [
        migrations.RunPython(merge_duplicates, noop_reverse),
    ]
