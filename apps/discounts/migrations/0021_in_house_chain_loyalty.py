"""Auto-attach in-house loyalty Discounts to Place rows whose name matches
one of 8 well-known UAE chain brands. Each chain gets one Discount row
per matching Place tagged source_program=in_house with the chain's
official program name in the title and a link to the program's page in
external_url.

Match is case-insensitive `__icontains` on the Place.name. The
match-string is specific enough that false positives are unlikely
(e.g. "Costa Coffee" rather than just "Costa").

Idempotent: update_or_create on a deterministic discount slug per
(chain, place). Reverse drops every discount it created.
"""
from django.db import migrations


CHAINS = [
    {
        "match": "costa coffee",
        "program_label": "Costa Coffee Club",
        "url": "https://www.costacoffee.ae",
        "headline_pct": 10,
        "description": (
            "Earn 'beans' on every Costa Coffee UAE purchase via the Costa "
            "Coffee Club app; 2,000 free beans on signup, redeem for free "
            "drinks. Available at all Costa UAE branches."
        ),
    },
    {
        "match": "tim hortons",
        "program_label": "Tim Hortons Rewards",
        "url": "https://timhortonsgcc.com",
        "headline_pct": 10,
        "description": (
            "Earn points and e-Wallet credit on every Tim Hortons UAE order "
            "via the Tims app. Redeem for menu items, drinks, and exclusive "
            "in-app deals."
        ),
    },
    {
        "match": "starbucks",
        "program_label": "Starbucks Rewards",
        "url": "https://www.starbucks.ae",
        "headline_pct": 10,
        "description": (
            "Earn Stars on every Starbucks UAE purchase. Redeem for "
            "handcrafted drinks, food, and at-home coffee. Free birthday "
            "drink and double-Star promotions throughout the year."
        ),
    },
    {
        "match": "pickl",
        "program_label": "Pickl Rewards",
        "url": "https://pickl.com",
        "headline_pct": 10,
        "description": (
            "Pickl's in-house rewards program — earn on every burger order, "
            "exclusive offers via the Pickl app."
        ),
    },
    {
        "match": "pizza hut",
        "program_label": "Hut Rewards",
        "url": "https://www.pizzahut.ae",
        "headline_pct": 10,
        "description": (
            "Earn points per AED spent on Pizza Hut UAE orders; redeem for "
            "free pizzas, sides, drinks. Available via the Pizza Hut app."
        ),
    },
    {
        "match": "mcdonald",
        "program_label": "MyMcDonald's Rewards",
        "url": "https://www.mcdonalds.com/ae",
        "headline_pct": 10,
        "description": (
            "Earn points on every McDonald's UAE order via the McDonald's "
            "app. Redeem for free menu items at any UAE branch."
        ),
    },
    {
        "match": "operation falafel",
        "program_label": "Operation Falafel Rewards",
        "url": "https://www.operationfalafel.com",
        "headline_pct": 10,
        "description": (
            "Earn rewards on every Operation Falafel visit via their "
            "loyalty app — discounts, free items, member-only offers."
        ),
    },
    {
        "match": "espresso lab",
        "program_label": "The Espresso Lab Loyalty",
        "url": "https://www.theespressolab.com",
        "headline_pct": 10,
        "description": (
            "Specialty coffee loyalty — earn on each visit to The Espresso "
            "Lab UAE. Redeem points for free drinks and merch."
        ),
    },
]


def slugify(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:80]


def attach_chain_loyalty(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")

    for chain in CHAINS:
        matches = Place.objects.filter(name__icontains=chain["match"])
        for place in matches:
            slug = ("in-" + slugify(chain["match"]) + "-" + place.slug)[:200]
            Discount.objects.update_or_create(
                slug=slug,
                defaults={
                    "place": place,
                    "title": f"{chain['program_label']} — earn points & rewards",
                    "discount_type": "percentage",
                    "percentage": chain["headline_pct"],
                    "source_program": "in_house",
                    "description": chain["description"],
                    "terms": (
                        "Points-based loyalty — the headline % is an "
                        "indicative effective rebate. See the chain's app "
                        "for the live earn/redeem rates."
                    ),
                    "external_url": chain["url"],
                    "is_active": True,
                    "is_featured": False,
                },
            )


def detach_chain_loyalty(apps, schema_editor):
    """Reverse: drop only the in-house discounts we created here, matched by
    the unique slug prefix `in-<chain>-`."""
    Discount = apps.get_model("discounts", "Discount")
    for chain in CHAINS:
        prefix = "in-" + slugify(chain["match"]) + "-"
        Discount.objects.filter(slug__startswith=prefix).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0020_seed_new_programs_and_tiers"),
    ]

    operations = [
        migrations.RunPython(attach_chain_loyalty, detach_chain_loyalty),
    ]
