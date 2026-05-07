"""Generate apps/discounts/migrations/0025_refresh_fazaa_from_api.py from
data/fazaa_api_parsed.json.

This migration upgrades every Fazaa Place + Discount from the Google-title
parsed data (migration 0023) to API-sourced data: real partner name, real
address, real website, exact discount value/type, expiry date, full T&Cs.

Strategy (idempotent):
- For each Place in the new dataset: update_or_create on slug. Updates
  category/area/address/website/description from API.
- For each Discount: update_or_create on the same `fazaa-{slug}` slug. The
  refreshed row gets the new discount_type, percentage, valid_until, and
  description.

Reverse: no-op. The 0023 reverse handles cleanup of all fazaa-* rows; this
migration only refreshes existing rows in place.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "data" / "fazaa_api_parsed.json"
DEST = ROOT / "apps" / "discounts" / "migrations" / "0025_refresh_fazaa_from_api.py"


def py_repr_list(lst, indent="    "):
    out = ["["]
    for d in lst:
        out.append(f"{indent}{{")
        for k, v in d.items():
            out.append(f"{indent}    {k!r}: {v!r},")
        out.append(f"{indent}}},")
    out.append(f"{indent[:-4]}]")
    return "\n".join(out)


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    places = data["places"]
    discounts = data["discounts"]

    body = f'''"""Refresh Fazaa data with API-sourced JSON, replacing the
title-parsed data from migration 0023.

For each known Fazaa offer slug we have cached JSON for, this migration
updates the Place (real partner name, real address, real website, real
city) and the Discount (exact discount value/type, expiry, full T&Cs).

Idempotent: update_or_create on slug.
Reverse: no-op (the 0023 reverse already drops every fazaa-* row).
"""
import re

from django.db import migrations


PLACES = {py_repr_list(places)}


DISCOUNTS = {py_repr_list(discounts)}


def normalize_for_dedup(name):
    n = name.lower()
    n = re.sub(r"\\bst\\b\\.?", "street", n)
    n = re.sub(r"\\bave\\b\\.?", "avenue", n)
    n = re.sub(r"\\brd\\b\\.?", "road", n)
    n = re.sub(r"\\b&\\b", "and", n)
    n = re.sub(r"[^a-z0-9]+", "", n)
    return n


def refresh_fazaa(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")

    # Lookup: existing Place rows by normalized name. We use this to find
    # venues that have a different slug from what API-driven parse produces
    # (e.g. an Entertainer Place with the same brand under a different slug).
    existing_by_norm = {{}}
    for p in Place.objects.all().only("id", "name", "slug"):
        existing_by_norm.setdefault(normalize_for_dedup(p.name), p)

    place_by_slug = {{}}
    for spec in PLACES:
        norm = normalize_for_dedup(spec["name"])
        existing = existing_by_norm.get(norm)
        if existing is not None:
            # Only refresh fields that the API can authoritatively give us;
            # don't overwrite things like phone/is_published if they were
            # set elsewhere.
            updated = False
            if not existing.address and spec["address"]:
                existing.address = spec["address"][:1000]
                updated = True
            if not existing.website and spec["website"]:
                existing.website = spec["website"]
                updated = True
            # Always trust the API's area — fixes "UAE" → "Dubai" etc.
            if existing.area != spec["area"]:
                existing.area = spec["area"]
                updated = True
            if updated:
                existing.save()
            place_by_slug[spec["slug"]] = existing
            continue

        place, _ = Place.objects.update_or_create(
            slug=spec["slug"],
            defaults={{
                "name": spec["name"],
                "category": spec["category"],
                "area": spec["area"],
                "address": spec["address"][:1000] if spec.get("address") else "",
                "website": spec["website"][:200] if spec.get("website") else "",
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
            "terms": d["terms"],
            "external_url": d["external_url"],
            "is_active": True,
            "is_featured": d.get("is_featured", False),
        }}
        if d.get("percentage") is not None:
            defaults["percentage"] = d["percentage"]
        else:
            defaults["percentage"] = None
        if d.get("valid_until"):
            defaults["valid_until"] = d["valid_until"]
        Discount.objects.update_or_create(
            slug=d["discount_slug"],
            defaults=defaults,
        )


def noop(apps, schema_editor):
    """No reverse — migration 0023's reverse already drops fazaa-* rows."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0024_add_jamies_italian"),
        ("places", "0004_seed_experiences_and_autotag"),
    ]

    operations = [
        migrations.RunPython(refresh_fazaa, noop),
    ]
'''

    DEST.write_text(body, encoding="utf-8")
    print(f"wrote {DEST}")
    print(f"  places: {len(places)}, discounts: {len(discounts)}")


if __name__ == "__main__":
    main()
