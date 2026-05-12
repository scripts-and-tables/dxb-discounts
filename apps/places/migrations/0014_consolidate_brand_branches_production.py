"""One-shot: consolidate brand-with-N-branches duplicate Places on prod.

Builds on migration 0013 which handled cross-source pairs (Kanpai +
Kanpai Dubai etc.). This migration handles the much larger pattern:
one chain × many physical outlets, where Entertainer's per-outlet
ingest creates a separate Place for every branch.

Examples (from local apply log):
- "360 Play" (Fazaa brand row) + 4 Entertainer branch rows -> collapsed
  into one Place.
- "Krispy Kreme" + 49 branches -> one Place.
- "ACAI Luv" (no brand row) -> synthesized brand Place + 10 branches
  merged in.

Local apply collapsed 262 clusters across 3 passes: 1,543 Place rows
soft-deleted and 3,947 Discounts re-pointed.

How it runs:
1. Generates data/place_duplicates_enriched.json by running the
   audit_place_duplicates script in-process (Django is already up).
2. Calls `merge_places --apply` to consolidate auto-merge clusters.
3. Repeats up to 3 times: each pass exposes new brand_with_branches
   cases that were hidden by the previous shape of the data.

Each pass is idempotent — re-running with zero residual auto-merge
clusters is a no-op. Safe to retry.
"""
import sys
from pathlib import Path

from django.core.management import call_command
from django.db import migrations


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def consolidate(apps, schema_editor):
    from scripts.audit_place_duplicates import audit

    for pass_num in range(1, 4):
        print(f"\n=== consolidate pass {pass_num} ===")
        n_clusters = audit()
        if n_clusters == 0:
            print(f"  no clusters; stopping after pass {pass_num - 1}.")
            break
        call_command("merge_places", apply=True)


def noop_reverse(apps, schema_editor):
    """Leaves the DB as-is. We don't want to silently un-soft-delete
    losers or move discounts back on rollback."""
    return


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("places", "0013_merge_duplicate_places_production"),
    ]

    operations = [
        migrations.RunPython(consolidate, noop_reverse),
    ]
