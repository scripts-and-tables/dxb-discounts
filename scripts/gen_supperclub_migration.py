"""Generate apps/discounts/migrations/0009_replace_supper_club_with_sitemap.py
from the parsed sitemap data."""
import json
import os
import sys
from pathlib import Path
from textwrap import dedent

TMP = os.environ.get("TEMP", "/tmp")
SRC = Path(TMP, "sc-parsed.json")
DEST = Path("apps/discounts/migrations/0009_replace_supper_club_with_sitemap.py")

# Hand-curated slugs from migration 0008 — delete these so we don't end up
# with two Place rows for the same venue (one hand-curated, one auto-parsed).
PURGE_PLACE_SLUGS_FROM_0008 = [
    "the-hide-jumeirah-al-qasr",
    "fluid-beach-club-th8-palm",
    "mimis-pool-club-five-jumeirah-village",
    "prime68-jw-marriott-marquis",
    "great-british-restaurant-dukes-the-palm",
    "crescendo-anantara-the-palm",
    "jw-kitchen-jw-marriott-marina",
    "solo-raffles-dubai",
    "ikandy-shangri-la-dubai",
    "conrad-dubai-pool",
    "jw-marriott-marquis-pool",
]


def py_repr_list(lst, indent=4):
    """Render a list of dicts as multi-line Python literal."""
    pad = " " * indent
    out = ["["]
    for d in lst:
        out.append(f"{pad}{{")
        for k, v in d.items():
            out.append(f"{pad}    {k!r}: {v!r},")
        out.append(f"{pad}}},")
    out.append(f"{' ' * (indent - 4) if indent >= 4 else ''}]")
    return "\n".join(out)


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    places = data["places"]
    discounts = data["discounts"]

    body = f'''"""Replace the 11 hand-curated Supper Club Place rows from migration 0008 with
the full ~156 Dubai venues parsed from supperclubme.com's sitemap, with their
real og:title offers attached as Discount rows.

The hand-curated Place rows from 0008 are deleted by slug; their dependent
Discount rows cascade. Then we upsert the sitemap-based catalog.

Idempotent: re-running the upsert on slug. Reverse deletes the rows added
by this migration."""

from django.db import migrations


PURGE_FROM_0008 = {PURGE_PLACE_SLUGS_FROM_0008!r}


PLACES = {py_repr_list(places, 0)}


DISCOUNTS = {py_repr_list(discounts, 0)}


def replace_supper_club(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")

    # Drop the hand-curated Supper Club Places from 0008 (cascades their Discounts).
    Place.objects.filter(slug__in=PURGE_FROM_0008).delete()

    # Upsert sitemap-based Places.
    place_by_slug = {{}}
    for spec in PLACES:
        place, _ = Place.objects.update_or_create(
            slug=spec["slug"],
            defaults={{
                "name": spec["name"],
                "category": spec["category"],
                "area": spec["area"],
                "address": spec.get("address", ""),
                "phone": spec.get("phone", ""),
                "website": spec.get("website", ""),
                "description": spec.get("description", ""),
                "is_published": True,
            }},
        )
        place_by_slug[spec["slug"]] = place

    # Upsert sitemap-based Discounts.
    for d in DISCOUNTS:
        place = place_by_slug.get(d["place_slug"])
        if place is None:
            continue
        Discount.objects.update_or_create(
            slug=d["discount_slug"],
            defaults={{
                "place": place,
                "title": d["title"][:200],
                "discount_type": d["discount_type"],
                "percentage": d.get("percentage"),
                "source_program": "supper_club",
                "description": d["description"],
                "terms": d["terms"],
                "is_active": True,
                "is_featured": False,
            }},
        )


def reverse_replace(apps, schema_editor):
    """Remove the rows added by this migration. We do NOT recreate the
    hand-curated 0008 entries on rollback; they can be re-added manually if
    needed."""
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")
    Discount.objects.filter(slug__in=[d["discount_slug"] for d in DISCOUNTS]).delete()
    Place.objects.filter(slug__in=[p["slug"] for p in PLACES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0008_add_supper_club_venues"),
    ]

    operations = [
        migrations.RunPython(replace_supper_club, reverse_replace),
    ]
'''

    DEST.write_text(body, encoding="utf-8")
    print(f"wrote {DEST} ({len(places)} places, {len(discounts)} discounts)")


if __name__ == "__main__":
    main()
