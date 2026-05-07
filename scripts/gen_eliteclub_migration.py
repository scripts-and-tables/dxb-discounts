"""Generate apps/discounts/migrations/0018_add_eliteclub_venues.py from
the Elite Club Dubai brochure parse."""
import json
import os
from pathlib import Path

TMP = Path(os.environ.get("TEMP", "/tmp"))
SRC = Path(os.environ.get("EC_PARSED", str(TMP / "ec-parsed.json")))
DEST = Path("apps/discounts/migrations/0018_add_eliteclub_venues.py")


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

    body = f'''"""Add Dubai partner hotels from Elite Club's public UAE brochure PDF.

Source: store.eliteclub.global/wp-content/uploads/2024/10/EC-UAE-BROCHURE
(89 pages — sections per emirate). Pages 4..45 are Dubai venues; one
hotel per page with Room/Food/Spa/Gym/Beverage benefit percentages.
The headline % stored on the Discount is the highest of those (FOOD
preferred since dining is the most relatable filter).

Idempotent: get_or_create on Place (preserves any existing rows that
share a slug — for example a hotel already imported from Supper Club),
update_or_create on Discount.

Reverse drops only the rows we added here, matched by slug.
"""

from django.db import migrations


PLACES = {py_repr_list(places)}


DISCOUNTS = {py_repr_list(discounts)}


def add_eliteclub(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")

    place_by_slug = {{}}
    for spec in PLACES:
        place, _ = Place.objects.get_or_create(
            slug=spec["slug"],
            defaults={{
                "name": spec["name"],
                "category": "hotel",
                "area": spec["area"],
                "address": "",
                "phone": "",
                "website": "",
                "description": (
                    f'{{spec["name"]}} — Dubai partner of Elite Club. Members '
                    f'get tiered discounts on rooms, dining, spa and more — '
                    f'see the EC UAE brochure on store.eliteclub.global for '
                    f'current offers.'
                ),
                "is_published": True,
            }},
        )
        place_by_slug[spec["slug"]] = place

    for d in DISCOUNTS:
        place = place_by_slug.get(d["place_slug"])
        if place is None:
            continue
        Discount.objects.update_or_create(
            slug=d["discount_slug"],
            defaults={{
                "place": place,
                "title": d["title"][:200],
                "discount_type": "percentage",
                "percentage": d["headline_pct"],
                "source_program": "elite_club",
                "description": (
                    f'Elite Club members benefit from: {{d["bullet"]}}. '
                    f'Each percentage applies to the named category — book '
                    f'via the Elite Club app to redeem.'
                ),
                "terms": (
                    "Discount tiers depend on Elite Club membership level "
                    "(Silver / Gold / Platinum). See the EC UAE brochure "
                    "for the latest offer matrix and exclusions."
                ),
                "external_url": "https://store.eliteclub.global/en/uae/",
                "is_active": True,
                "is_featured": False,
            }},
        )


def remove_eliteclub(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")
    Discount.objects.filter(slug__in=[d["discount_slug"] for d in DISCOUNTS]).delete()
    Place.objects.filter(slug__in=[p["slug"] for p in PLACES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0017_more_entertainer_venues"),
        ("places", "0004_seed_experiences_and_autotag"),
    ]

    operations = [
        migrations.RunPython(add_eliteclub, remove_eliteclub),
    ]
'''

    DEST.write_text(body, encoding="utf-8")
    print(f"wrote {DEST} ({len(places)} places, {len(discounts)} discounts)")


if __name__ == "__main__":
    main()
