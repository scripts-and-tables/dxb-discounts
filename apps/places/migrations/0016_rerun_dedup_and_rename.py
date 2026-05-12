"""One-shot: clean up residual duplicates on prod.

Two passes:
1. Rename synthesized brand Places whose name was derived from the
   normalized cluster_id (e.g. "Adventure Zone Adventure") using the
   character-level longest common prefix of their original branches'
   names instead (e.g. "Adventure Zone by Adventure HQ").
2. Re-run audit + merge once more. After the Playbook removal in
   migration 0015 some new brand-with-branches clusters may be
   reachable (Places that had Playbook discounts and thus appeared in
   different audit shapes). This pass converges them.

Idempotent: running again is a no-op.
"""
from django.core.management import call_command
from django.db import migrations


def cleanup(apps, schema_editor):
    # 1) Rename mis-synthesized brands.
    call_command("rename_synthesized_brands", apply=True)

    # 2) One more audit+merge pass. May be a no-op if nothing eligible.
    from scripts.audit_place_duplicates import audit
    n = audit()
    if n > 0:
        call_command("merge_places", apply=True)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("places", "0015_remove_playbook_data"),
    ]

    operations = [
        migrations.RunPython(cleanup, noop_reverse),
    ]
