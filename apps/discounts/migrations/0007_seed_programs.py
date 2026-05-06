"""Seed the 11 UAE discount programs that the /discounts/ directory shows.

Idempotent: re-running upserts on slug. Reverse deletes only the slugs we
introduced here.
"""

from django.db import migrations


PROGRAMS = [
    {
        "slug": "fazaa",
        "name": "Fazaa",
        "short_description": "UAE-wide discount card from the Ministry of Interior. Free family memberships available in 2026 via the Year of the Family initiative.",
        "description": (
            "Fazaa is a multi-tier discount card (Discount / Silver / Gold / "
            "Platinum) covering hundreds of outlets across dining, retail, "
            "travel, healthcare and entertainment. Originally for UAE military "
            "and government employees and their families; Year of the Family "
            "2026 expanded access to all UAE resident families."
        ),
        "official_url": "https://www.fazaa.ae",
        "cost_summary": "Free / paid tiers",
        "eligibility": "UAE residents (military / gov priority)",
        "sort_order": 10,
    },
    {
        "slug": "esaad",
        "name": "Esaad",
        "short_description": "Dubai Police privilege card with 8,000+ partners across the UAE and abroad.",
        "description": (
            "Launched in 2017 by Dubai Police as a welfare initiative, Esaad "
            "has grown into a major lifestyle card with discounts at thousands "
            "of partners spanning dining, retail, hotels and services. "
            "Expanded over the years to include Golden Visa holders and other "
            "categories beyond the original government-employee scope."
        ),
        "official_url": "https://esaad.dubaipolice.gov.ae",
        "cost_summary": "Free for eligible holders",
        "eligibility": "Dubai Police / gov employees / Golden Visa holders",
        "sort_order": 20,
    },
    {
        "slug": "entertainer",
        "name": "The Entertainer",
        "short_description": "BOGOF voucher app — buy-one-get-one-free deals at hundreds of restaurants, attractions and spas.",
        "description": (
            "Originally a printed voucher book, now a subscription app. "
            "Members get unlimited buy-one-get-one-free redemptions on dining, "
            "casual eats, attractions, fitness and beauty across Dubai and "
            "Abu Dhabi for the year their subscription is valid."
        ),
        "official_url": "https://www.theentertainerme.com",
        "cost_summary": "Paid subscription",
        "eligibility": "Anyone",
        "sort_order": 30,
    },
    {
        "slug": "zomato",
        "name": "Zomato Pro / Gold",
        "short_description": "Restaurant subscription offering complimentary dishes, drinks or percentage discounts at partner outlets.",
        "description": (
            "Zomato's paid dining membership for the UAE. Members get "
            "complimentary food/drink items or flat percentage discounts at "
            "participating restaurants — visible inside the Zomato app at the "
            "moment of booking or order."
        ),
        "official_url": "https://www.zomato.com",
        "cost_summary": "Paid",
        "eligibility": "Anyone",
        "sort_order": 40,
    },
    {
        "slug": "repeat",
        "name": "Repeat",
        "short_description": "Personalised dining loyalty — your discount grows the more frequently you visit.",
        "description": (
            "UAE-built free loyalty app that gives every member a personalised "
            "discount at participating cafés and restaurants based on how "
            "often they return and how much they spend. No vouchers — the "
            "discount is applied directly to the bill."
        ),
        "official_url": "https://repeat.app",
        "cost_summary": "Free",
        "eligibility": "Anyone",
        "sort_order": 50,
    },
    {
        "slug": "elite_club",
        "name": "Elite Club",
        "short_description": "Premium dining and travel membership across 120+ UAE hotels and 2,000+ GCC restaurants.",
        "description": (
            "Tiered membership (Silver / Gold / Platinum) with an extensive "
            "voucher library: dining cash vouchers, lunch and dinner "
            "invitations for two, dessert and welcome-drink vouchers, plus "
            "BOGOF redemptions. One voucher per visit; BOGOF redemptions are "
            "unlimited."
        ),
        "official_url": "https://store.eliteclub.global/en/uae/",
        "cost_summary": "Paid (Silver / Gold / Platinum tiers)",
        "eligibility": "Anyone",
        "sort_order": 60,
    },
    {
        "slug": "supper_club",
        "name": "Supper Club ME",
        "short_description": "Premium dining membership — up to 68% off at 5-star restaurants, spas and staycations.",
        "description": (
            "Founded in Dubai in 2020. Three tiers (Gold / Diamond / Platinum) "
            "covering 150+ offers across 30+ five-star hotels in Dubai and "
            "Abu Dhabi. Discounts apply automatically at the venue — no codes "
            "or vouchers."
        ),
        "official_url": "https://supperclubme.com",
        "cost_summary": "From AED 275/year",
        "eligibility": "Anyone",
        "sort_order": 70,
    },
    {
        "slug": "emirates_platinum",
        "name": "Emirates Platinum",
        "short_description": "Lifestyle privilege card for Emirates Group employees and their dependents.",
        "description": (
            "Launched in 2008 for Emirates airline staff and subsidiaries. "
            "Each employee can add up to 3 dependants. Offers dining, retail, "
            "leisure and entertainment discounts across Dubai venues, "
            "including discounted brunches and à la carte menus."
        ),
        "official_url": "https://www.platinumcardoffers.com",
        "cost_summary": "Free for eligible holders",
        "eligibility": "Emirates Group employees + dependents",
        "sort_order": 80,
    },
    {
        "slug": "shukran",
        "name": "Shukran",
        "short_description": "Landmark Group's free loyalty program — 13M+ members across the region.",
        "description": (
            "Shukran rewards points (\"Shukrans\") earned at Landmark Group "
            "brands such as Centrepoint, Max, Home Centre, Babyshop and "
            "Splash, plus partner brands. Two membership tiers (Silver, Gold). "
            "Points can be redeemed at checkout. Partnered with ADNOC and "
            "Qashio for cross-program point exchange."
        ),
        "official_url": "https://www.shukran.com",
        "cost_summary": "Free",
        "eligibility": "Anyone",
        "sort_order": 90,
    },
    {
        "slug": "share_rewards",
        "name": "SHARE Rewards",
        "short_description": "Majid Al Futtaim loyalty — earn and redeem points at Carrefour, MOE, City Centre malls, VOX, Ski Dubai.",
        "description": (
            "Free loyalty program covering 5,000+ stores in Majid Al Futtaim's "
            "ecosystem: Mall of the Emirates, City Centre malls, Carrefour, "
            "VOX Cinemas, Magic Planet, Ski Dubai, LEGO Certified, and more. "
            "Earn 2.5–150 SHARE points per AED 100 spent. Family groups of "
            "up to 9 members can pool points."
        ),
        "official_url": "https://www.sharerewards.com",
        "cost_summary": "Free",
        "eligibility": "Anyone",
        "sort_order": 100,
    },
    {
        "slug": "emirates_skywards",
        "name": "Emirates Skywards",
        "short_description": "Emirates airline's loyalty program — earn miles on flights and at 400+ UAE retail/dining brands.",
        "description": (
            "Free airline loyalty program. Skywards Everyday lets members "
            "earn up to 1 Mile for every AED 3 spent at 400+ UAE brands "
            "spanning dining, retail and lifestyle. Points convertible with "
            "Accor's ALL Reward Points and Emarat's EmCoins."
        ),
        "official_url": "https://www.emirates.com/skywards",
        "cost_summary": "Free",
        "eligibility": "Anyone",
        "sort_order": 110,
    },
]


def seed_programs(apps, schema_editor):
    Program = apps.get_model("discounts", "Program")
    for spec in PROGRAMS:
        Program.objects.update_or_create(
            slug=spec["slug"],
            defaults={k: v for k, v in spec.items() if k != "slug"},
        )


def remove_seeded_programs(apps, schema_editor):
    Program = apps.get_model("discounts", "Program")
    Program.objects.filter(slug__in=[p["slug"] for p in PROGRAMS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0006_add_program_and_extend_choices"),
    ]

    operations = [
        migrations.RunPython(seed_programs, remove_seeded_programs),
    ]
