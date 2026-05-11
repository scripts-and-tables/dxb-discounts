"""One-shot: ingest Fazaa + Playbook into the production DB, then re-apply
the resolved icon overrides so the newly-created Place rows pick up the
logo URLs that already exist in data/place_icons_enriched.json.

Background: migration 0009 ingested Entertainer on prod, but the Fazaa
and Playbook source programs were only ever ingested locally. As a
result, the previous icon-apply migration (0011) found ~4,700 Places
in the local enriched JSON whose slugs didn't exist on prod yet —
those rows were skipped. After this migration, prod has the same set
of Places as local, so the second `apply_resolved_icons` pass picks
them up.

Inputs (must be present at migration time; revert in a follow-up commit
once prod has applied — same pattern as 0009):
  data/fazaa_search_enriched.json
  data/playbook_search_enriched.json
  data/place_icons_enriched.json  (already committed in earlier work)

The migration is non-atomic because `ingest_offers` manages its own
transactions per source. The icon-apply step uses a plain bulk_update.

Idempotent: both ingest_offers and apply_resolved_icons are safe to
re-run — they upsert by stable slug and skip targets already set.
"""
import importlib

from django.core.management import call_command
from django.db import migrations


def ingest_and_apply(apps, schema_editor):
    # 1) Ingest Fazaa first (~4,238 partners, ~4,238 discounts), then
    # Playbook (~1,490 venues, ~5,000 highlight discounts). Each takes
    # ~30-60s on Railway's small DB.
    call_command("ingest_offers", source="fazaa", skip_backfill=True)
    call_command("ingest_offers", source="playbook", skip_backfill=True)

    # 2) Re-run the icon applier. Migration 0011 still ran end-to-end on
    # prod last time, but skipped 4,698 rows due to slug-not-found. Now
    # those slugs exist (created by step 1 above), so this pass fills
    # them in. The function is defined in migration 0011 — import via
    # importlib because the module name starts with a digit.
    apply_mod = importlib.import_module(
        "apps.places.migrations.0011_apply_place_icons_production"
    )
    apply_mod.apply_resolved_icons(apps, schema_editor)


def noop_reverse(apps, schema_editor):
    """Reverse leaves the DB as-is. Ingest created rows we don't want
    to silently delete; logo overrides similarly stay put."""
    return


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("places", "0011_apply_place_icons_production"),
    ]

    operations = [
        migrations.RunPython(ingest_and_apply, noop_reverse),
    ]
