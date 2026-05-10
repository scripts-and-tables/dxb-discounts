"""Remove the 21 referral programs whose URLs turned out to be broken.

The initial Refer & Earn seed (migration 0031) was loaded with --include-review,
which forced through entries the verifier had flagged. Production traffic
quickly surfaced that several never had a public referral page (Amazon.ae,
Carrefour UAE — both run only affiliate/loyalty programs, no consumer
referral) and others returned 404 / Cloudflare-gated when actually visited
in a browser. Rather than continue patching individual URLs, we drop the
unverified entries and rebuild the directory from a curated, hand-verified
seed.

The four entries left after this migration are the ones we have direct
evidence for: Careem Pay, Mashreq NEO, ADCB Hayyak, and Etisalat by e&.

Removed brands' Discount + Place rows are deleted by slug. Reverse leaves
data unchanged — re-add brands by editing data/referral_seed.json and
re-running scripts/gen_referrals_migration.py."""
from django.db import migrations


REMOVED_PLACE_SLUGS = [
    "talabat",
    "noon",
    "deliveroo",
    "kibsons",
    "instashop",
    "carrefour-uae",
    "amazon-ae",
    "liv-bank",
    "du-uae",
    "rain-payments",
    "yap-uae",
    "rehlat",
    "cobone",
    "fitness-first-uae",
    "warehouse-gym",
    "the-little-gym-dubai",
    "kidzania-dubai",
    "privilee",
    "the-select-app",
    "washmen",
    "justlife",
]


def remove_broken(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")
    discount_slugs = [f"{slug}-referral" for slug in REMOVED_PLACE_SLUGS]
    Discount.objects.filter(slug__in=discount_slugs).delete()
    Place.objects.filter(slug__in=REMOVED_PLACE_SLUGS).delete()


def noop_reverse(apps, schema_editor):
    """Reverse leaves the DB as-is — the removed entries had broken URLs and
    shouldn't be silently reanimated."""
    return


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0031_seed_referrals"),
        ("places", "0008_set_aggregator_flag_for_legacy_brands"),
    ]

    operations = [
        migrations.RunPython(remove_broken, noop_reverse),
    ]
