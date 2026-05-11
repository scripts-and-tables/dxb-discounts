"""One-shot: run ingest_offers + consolidate_legacy_offers against the production DB.

Background: the new per-offer Entertainer ingest (commit 29cdce3) was run
locally but never on production. Production still holds only the legacy
'Buy One Get One Free at <brand> via The Entertainer' generic rows from
migrations 0015-0017. Migration 0008's brand-rollup never had anything to
roll up there because no branch Places existed.

This migration invokes the same management commands we use locally:

    python manage.py ingest_offers --source entertainer --skip-backfill
    python manage.py consolidate_legacy_offers

It reads data/entertainer_outlets_enriched.json (committed once with this
migration; reverted in a follow-up commit after this has applied to prod).

Once applied, production has ~7,300 per-offer Discount rows attached to
~3,000 branch Places, with ~184 legacy brand Places flagged
`aggregates_branches=True` (their detail pages roll up the branch rows).

The migration is non-atomic because the management commands manage their
own transactions; nesting Django's atomic around call_command's atomic on
Postgres works via savepoints but we prefer to let the inner code own the
boundary.

Idempotent: re-running is safe (update_or_create on stable slugs)."""
from django.core.management import call_command
from django.db import migrations


def ingest_entertainer(apps, schema_editor):
    call_command("ingest_offers", source="entertainer", skip_backfill=True)
    call_command("consolidate_legacy_offers")


def noop_reverse(apps, schema_editor):
    """Reverse leaves the DB as-is. The ingest created rows we don't want to
    silently delete on rollback — manual cleanup if needed."""
    return


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("places", "0008_set_aggregator_flag_for_legacy_brands"),
        ("discounts", "0033_seed_referrals"),
    ]

    operations = [
        migrations.RunPython(ingest_entertainer, noop_reverse),
    ]
