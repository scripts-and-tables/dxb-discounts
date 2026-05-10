"""Generate the Django data migration that upserts the curated UAE referral
programs from data/referrals_enriched.json.

Reads the enriched JSON produced by `python scripts/verify_referrals.py` and
emits a single migration:

    apps/discounts/migrations/<NEXT>_seed_referrals.py

The migration upserts:
- one Program row with slug="referral" (the cross-place directory entry)
- one Place row per brand (idempotent on slug)
- one Discount row per brand (idempotent on slug, type=referral, source_program=referral)

Idempotent: re-running the generator overwrites the migration file. Re-running
the migration upserts on slug. Reverse deletes only the rows added here.

The script does NOT apply the migration; review the generated file and run
`python manage.py migrate` yourself.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "referrals_enriched.json"
MIG_DIR = ROOT / "apps" / "discounts" / "migrations"

REFERRAL_PROGRAM = {
    "slug": "referral",
    "name": "Refer & Earn",
    "short_description": (
        "Brand referral programs for UAE services — share your code, both "
        "you and your friend earn credit, cashback, or free months."
    ),
    "description": (
        "A curated directory of public Refer-a-Friend programs from UAE "
        "apps and services. Each entry links to the brand's official "
        "referral page where you can sign in, get your unique code, and "
        "share it. Most programs reward both sides of the referral — "
        "credit, cashback, free data, or a complimentary month — when "
        "the friend completes their first qualifying purchase or signup.\n\n"
        "We only list programs whose terms are publicly published. Codes "
        "themselves are per-user and rotate, so they're not stored here — "
        "tap through to the brand's page to grab yours."
    ),
    "official_url": "",
    "cost_summary": "Free",
    "eligibility": "Anyone with an account on the underlying brand",
    "sort_order": 80,
    "tiers": [],
    "expected_savings": (
        "Typical bonuses range from AED 20–100 per successful referral, "
        "or one free month of membership for fitness/lifestyle programs. "
        "Active referrers can stack AED 200–500 in credits per year across "
        "delivery, fintech, and telco programs."
    ),
}

ALLOWED_CATEGORIES = {"restaurant", "attraction", "hotel", "retail", "service"}


def slug_from_url(url: str) -> str:
    """Strip 'https://www.' and trailing slash to derive a stable website
    field — matches how Place.logo_domain works."""
    return url


def next_migration_number() -> int:
    nums = []
    for p in MIG_DIR.glob("[0-9][0-9][0-9][0-9]_*.py"):
        m = re.match(r"(\d{4})_", p.name)
        if m:
            nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


def latest_migration_name() -> str:
    """Return the last existing 'NNNN_name' (without .py) — used as the
    `dependencies` anchor for the new migration."""
    candidates = sorted(MIG_DIR.glob("[0-9][0-9][0-9][0-9]_*.py"))
    if not candidates:
        return "0001_initial"
    return candidates[-1].stem


def py_repr_list(lst, indent=0):
    pad = " " * indent
    out = ["["]
    for d in lst:
        out.append(f"{pad}    {{")
        for k, v in d.items():
            out.append(f"{pad}        {k!r}: {v!r},")
        out.append(f"{pad}    }},")
    out.append(f"{pad}]")
    return "\n".join(out)


def py_repr_dict(d, indent=0):
    pad = " " * indent
    out = ["{"]
    for k, v in d.items():
        out.append(f"{pad}    {k!r}: {v!r},")
    out.append(f"{pad}}}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--include-review", action="store_true",
                    help="Include entries flagged needs_review in the migration. "
                         "Default skips them so only verified entries land in the DB.")
    args = ap.parse_args()

    if not SRC.exists():
        print(f"missing {SRC} — run python scripts/verify_referrals.py first", file=sys.stderr)
        return 1

    enriched = json.loads(SRC.read_text(encoding="utf-8"))

    rows = []
    skipped = []
    for e in enriched:
        if e.get("needs_review") and not args.include_review:
            skipped.append((e["slug"], e.get("review_reason", "?")))
            continue
        cat = e.get("category", "service")
        if cat not in ALLOWED_CATEGORIES:
            skipped.append((e["slug"], f"invalid category {cat!r}"))
            continue
        rows.append(e)

    places = [
        {
            "slug": e["slug"],
            "name": e["name"],
            "category": e.get("category", "service"),
            "area": e.get("area", ""),
            "website": e.get("website", ""),
        }
        for e in rows
    ]
    discounts = [
        {
            "place_slug": e["slug"],
            "discount_slug": f"{e['slug']}-referral",
            "title": f"Refer & Earn — {e['name']}",
            "description": e.get("description", "").strip(),
            "external_url": e.get("referral_url", ""),
        }
        for e in rows
    ]

    next_num = next_migration_number()
    dest = MIG_DIR / f"{next_num:04d}_seed_referrals.py"
    dependency = latest_migration_name()

    body = f'''"""Seed the Refer & Earn program directory: one Program row + ~{len(rows)} Places
+ Discounts for curated UAE referral programs (Careem, Talabat, Mashreq NEO,
The Little Gym, etc.).

Generated by scripts/gen_referrals_migration.py from data/referrals_enriched.json.
Re-running the generator overwrites this file. The migration itself is
idempotent (upsert on slug)."""
from django.db import migrations


PROGRAM = {py_repr_dict(REFERRAL_PROGRAM, 0)}


PLACES = {py_repr_list(places, 0)}


DISCOUNTS = {py_repr_list(discounts, 0)}


def seed(apps, schema_editor):
    Program = apps.get_model("discounts", "Program")
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")

    Program.objects.update_or_create(
        slug=PROGRAM["slug"],
        defaults={{k: v for k, v in PROGRAM.items() if k != "slug"}},
    )

    place_by_slug = {{}}
    for spec in PLACES:
        place, _ = Place.objects.update_or_create(
            slug=spec["slug"],
            defaults={{
                "name": spec["name"],
                "category": spec["category"],
                "area": spec["area"],
                "website": spec.get("website", ""),
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
                "discount_type": "referral",
                "source_program": "referral",
                "description": d["description"],
                "external_url": d["external_url"],
                "is_active": True,
                "is_featured": False,
            }},
        )


def reverse(apps, schema_editor):
    Program = apps.get_model("discounts", "Program")
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")
    Discount.objects.filter(slug__in=[d["discount_slug"] for d in DISCOUNTS]).delete()
    Place.objects.filter(slug__in=[p["slug"] for p in PLACES]).delete()
    Program.objects.filter(slug=PROGRAM["slug"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "{dependency}"),
        ("places", "0006_alter_place_area_alter_place_category"),
    ]

    operations = [
        migrations.RunPython(seed, reverse),
    ]
'''

    dest.write_text(body, encoding="utf-8")
    print(f"wrote {dest}")
    print(f"  Program rows: 1 (slug=referral)")
    print(f"  Place rows: {len(places)}")
    print(f"  Discount rows: {len(discounts)}")
    if skipped:
        print(f"  skipped {len(skipped)} (re-run with --include-review to keep them):")
        for slug, reason in skipped:
            print(f"    {slug}: {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
