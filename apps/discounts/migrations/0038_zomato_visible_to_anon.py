"""Flip Zomato discounts to is_members_only=False so they render to
anonymous visitors.

0036 and 0037 set is_members_only=True on all Zomato seed discounts,
matching the *semantic* fact that you need Zomato Gold membership to
redeem them. But `is_members_only=True` *also* tells the place-detail
view to hide the row from anonymous (not-logged-in) visitors
(apps/places/views.py:65, :114).

The project convention for "loyalty program required" offers (Fazaa,
ADCB, Atlantis Circle) is to leave is_members_only=False and put the
membership requirement in the description/terms, so prospective
members can still browse the offers before signing up. Match that.

Idempotent: just flips the boolean.
"""
from django.db import migrations


def show_to_anon(apps, schema_editor):
    Discount = apps.get_model("discounts", "Discount")
    Discount.objects.filter(source_program="zomato").update(is_members_only=False)


def hide_from_anon(apps, schema_editor):
    Discount = apps.get_model("discounts", "Discount")
    Discount.objects.filter(source_program="zomato").update(is_members_only=True)


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0037_zomato_flat_seed"),
    ]

    operations = [
        migrations.RunPython(show_to_anon, hide_from_anon),
    ]
