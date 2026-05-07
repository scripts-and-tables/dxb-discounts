"""Generate apps/discounts/migrations/0023_seed_fazaa_offers.py from
data/fazaa_parsed.json.

For each parsed Fazaa offer:

1. If a Place already exists in the catalog whose name matches (after
   `normalize_for_dedup`), attach the Fazaa Discount to that Place.
2. Otherwise, create a new Place with category and area inferred at parse
   time, then create the Discount.

Reverse: drop only the discounts whose slug starts with 'fazaa-' and have
source_program='fazaa'. Do not delete the Places we created; they may have
gained other-program discounts since import.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "data" / "fazaa_parsed.json"
DEST = ROOT / "apps" / "discounts" / "migrations" / "0023_seed_fazaa_offers.py"


def py_repr_list(lst):
    out = ["["]
    for d in lst:
        out.append("    {")
        for k, v in d.items():
            out.append(f"        {k!r}: {v!r},")
        out.append("    },")
    out.append("]")
    return "\n".join(out)


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    places = data["places"]
    discounts = data["discounts"]

    body = f'''"""Seed Fazaa partner venues + discounts harvested via Google site-search
on fazaa.ae/offers/view (Fazaa is JS-rendered + Cloudflare-protected, so
the sitemap path used for Supper Club / Entertainer doesn't work here).

Each parsed row is matched against existing Place rows by normalized name
(`normalize_for_dedup`). Matched venues get the Fazaa Discount attached to
their existing Place. Unmatched venues are created as new Places.

Idempotent: get_or_create on Place slug, update_or_create on Discount slug.
Reverse drops only the Fazaa discounts; new Places are kept since they
may have gained discounts from other programs since this ran.
"""
import re

from django.db import migrations


PLACES = {py_repr_list(places)}


DISCOUNTS = {py_repr_list(discounts)}


def normalize_for_dedup(name: str) -> str:
    n = name.lower()
    n = re.sub(r"\\bst\\b\\.?", "street", n)
    n = re.sub(r"\\bave\\b\\.?", "avenue", n)
    n = re.sub(r"\\brd\\b\\.?", "road", n)
    n = re.sub(r"\\b&\\b", "and", n)
    n = re.sub(r"[^a-z0-9]+", "", n)
    return n


def add_fazaa(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")

    # Build a lookup of existing Places by normalized name so we can attach
    # Fazaa discounts to venues already in the catalog (Supper Club,
    # Entertainer, Elite Club, hand-curated rows, etc.).
    existing_by_norm = {{}}
    for p in Place.objects.all().only("id", "name", "slug"):
        existing_by_norm.setdefault(normalize_for_dedup(p.name), p)

    place_by_slug = {{}}
    for spec in PLACES:
        norm = normalize_for_dedup(spec["name"])
        existing = existing_by_norm.get(norm)
        if existing is not None:
            place_by_slug[spec["slug"]] = existing
            continue
        place, _ = Place.objects.get_or_create(
            slug=spec["slug"],
            defaults={{
                "name": spec["name"],
                "category": spec["category"],
                "area": spec["area"],
                "address": "",
                "phone": "",
                "website": "",
                "description": spec["description"],
                "is_published": True,
            }},
        )
        place_by_slug[spec["slug"]] = place

    for d in DISCOUNTS:
        place = place_by_slug.get(d["place_slug"])
        if place is None:
            continue
        defaults = {{
            "place": place,
            "title": d["title"][:200],
            "discount_type": d["discount_type"],
            "source_program": "fazaa",
            "description": d["description"],
            "terms": (
                "Present a valid Fazaa card. Headline percentage may vary "
                "by Fazaa tier (Platinum / Gold / Silver). See the offer "
                "page for the live terms."
            ),
            "external_url": d["external_url"],
            "is_active": True,
            "is_featured": False,
        }}
        if d["percentage"] is not None:
            defaults["percentage"] = d["percentage"]
        Discount.objects.update_or_create(
            slug=d["discount_slug"],
            defaults=defaults,
        )


def remove_fazaa(apps, schema_editor):
    """Remove Fazaa discounts. Leave the Places; they may have been linked
    to other programs after import (e.g. a future Esaad migration)."""
    Discount = apps.get_model("discounts", "Discount")
    Discount.objects.filter(
        slug__startswith="fazaa-",
        source_program="fazaa",
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0022_add_discount_type_other"),
        ("places", "0004_seed_experiences_and_autotag"),
    ]

    operations = [
        migrations.RunPython(add_fazaa, remove_fazaa),
    ]
'''

    DEST.write_text(body, encoding="utf-8")
    print(f"wrote {DEST} ({len(places)} places, {len(discounts)} discounts)")


if __name__ == "__main__":
    main()
