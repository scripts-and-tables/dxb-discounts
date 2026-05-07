"""Seed three new programs (Atlantis Circle, U By Emaar, Al-Futtaim Blue)
and backfill tier breakdowns + expected-savings text on every existing
Program row so the program detail pages can render a 'What you get by
tier' table.
"""
from django.db import migrations


NEW_PROGRAMS = [
    {
        "slug": "atlantis_circle",
        "name": "Atlantis Circle",
        "short_description": "Atlantis Dubai's free dining loyalty — 15% off restaurants on signup, scaling to 30% as you spend.",
        "description": (
            "The Atlantis Circle is the in-house loyalty program at Atlantis "
            "The Palm and Atlantis The Royal Dubai. Free to join via the "
            "Atlantis Circle app. The discount tier is determined by how "
            "much you spend at participating restaurants over a rolling "
            "12-month window. Tiers also unlock event invites, beach club "
            "access and birthday credit."
        ),
        "official_url": "https://www.atlantis.com/dubai/membership/atlantis-circle",
        "cost_summary": "Free",
        "eligibility": "Anyone (Dubai resident perks more pronounced)",
        "sort_order": 120,
        "tiers": [
            {"name": "Blue", "threshold": "Free signup",
             "benefit": "15% off restaurants"},
            {"name": "Silver", "threshold": "AED 12,000/year on dining",
             "benefit": "20% off restaurants + birthday credit"},
            {"name": "Gold", "threshold": "AED 25,000/year on dining",
             "benefit": "25% off restaurants + early-bird bookings + beach access perks"},
            {"name": "Black", "threshold": "AED 40,000/year on dining",
             "benefit": "30% off restaurants + exclusive event invitations"},
        ],
        "expected_savings": "A weekly diner at Blue tier saves ~AED 2,500–4,000 a year; the Black tier (heavy spenders) typically saves AED 12,000+.",
    },
    {
        "slug": "u_by_emaar",
        "name": "U By Emaar",
        "short_description": "Emaar Group's free loyalty across Address, Vida, Armani Hotel, At.Mosphere, Reel Cinemas, Dubai Aquarium and Dubai Mall dining.",
        "description": (
            "U By Emaar (formerly U Card) is the unified loyalty program "
            "across the Emaar group. Members earn Upoints on dining, hotel "
            "stays and entertainment at participating Emaar venues — Address "
            "Hotels & Resorts, Vida Hotels, Armani Hotel Dubai, At.Mosphere "
            "(Burj Khalifa), Reel Cinemas, Dubai Aquarium & Underwater Zoo, "
            "and dozens of Dubai Mall restaurants. 1 Upoint = AED 2 spent "
            "at participating restaurants. Tiers unlock priority benefits."
        ),
        "official_url": "https://www.ubyemaar.com",
        "cost_summary": "Free",
        "eligibility": "Anyone",
        "sort_order": 130,
        "tiers": [
            {"name": "Black", "threshold": "Free signup",
             "benefit": "Earn 1 Upoint per AED 2 at Emaar restaurants; basic offers"},
            {"name": "Silver", "threshold": "Earn 1,500+ Upoints in 12 months",
             "benefit": "Bigger redemption rates, seasonal promotions"},
            {"name": "Gold", "threshold": "Earn 5,000+ Upoints in 12 months",
             "benefit": "Premium offers, member-only events, faster point earning"},
            {"name": "Platinum", "threshold": "Earn 10,000+ Upoints in 12 months",
             "benefit": "Top-tier perks, exclusive experiences (VIP cinema seats, suite upgrades, etc.)"},
        ],
        "expected_savings": "Members typically earn back 5–10% as Upoints redeemable on Emaar venues. Heavy Dubai Mall diners can save AED 3,000–6,000/year.",
    },
    {
        "slug": "al_futtaim_blue",
        "name": "Blue (Al-Futtaim)",
        "short_description": "Free retail loyalty across Al-Futtaim Group brands — IKEA, ACE, Marks & Spencer, Plug-Ins, Lacoste, Toys R Us and many more.",
        "description": (
            "Blue is the loyalty program from Al-Futtaim Retail Group. Free "
            "to join via the Blue app. Earns 'infinite cashback' at "
            "participating Al-Futtaim brands across the UAE — IKEA, ACE "
            "Hardware, Marks & Spencer, Plug-Ins Electronix, Robinsons, "
            "Toys R Us, Lacoste, Frankly, Festival City and others. Members "
            "also get hundreds of 2-for-1 deals on dining and entertainment "
            "across the UAE."
        ),
        "official_url": "https://blue.alfuttaim.com",
        "cost_summary": "Free",
        "eligibility": "Anyone",
        "sort_order": 140,
        "tiers": [
            {"name": "Member", "threshold": "Free signup via the Blue app",
             "benefit": "Cashback on every Al-Futtaim brand purchase + 2-for-1 dining/entertainment deals + Blue Exclusive Offers"},
        ],
        "expected_savings": "Effective cashback rate ~3–5% across Al-Futtaim purchases. Households doing major IKEA / electronics / M&S spend can save AED 1,000–3,000/year.",
    },
]


# Tier backfill for existing programs.
EXISTING_PROGRAM_TIERS = {
    "fazaa": {
        "tiers": [
            {"name": "Discount Card", "threshold": "Free for resident families (Year of Family init)",
             "benefit": "Basic discounts at hundreds of UAE outlets"},
            {"name": "Silver", "threshold": "Paid annual subscription",
             "benefit": "All Discount benefits + hotels, travel, insurance discounts"},
            {"name": "Gold", "threshold": "Paid (higher tier)",
             "benefit": "More premium hotel + travel + healthcare benefits"},
            {"name": "Platinum", "threshold": "Paid (top tier)",
             "benefit": "Priority access to exclusive services + concierge"},
        ],
        "expected_savings": "Discount tier members typically save AED 500–1,500/year on dining; paid Silver+ tiers add hotel and travel value worth several thousand more.",
    },
    "esaad": {
        "tiers": [
            {"name": "Esaad", "threshold": "Free for eligible holders",
             "benefit": "~20% off at 8,000+ UAE and international partners (dining, retail, hotels, services)"},
        ],
        "expected_savings": "Active members typically save AED 2,000–5,000/year on dining and lifestyle spend.",
    },
    "entertainer": {
        "tiers": [
            {"name": "Annual subscription", "threshold": "Paid (≈AED 595/year for UAE)",
             "benefit": "Unlimited buy-one-get-one-free redemptions on dining, attractions, fitness, beauty across Dubai and Abu Dhabi"},
        ],
        "expected_savings": "Most subscribers break even after 4–5 BOGOF redemptions; active users save AED 3,000–5,000/year.",
    },
    "zomato": {
        "tiers": [
            {"name": "Pro / Gold", "threshold": "Paid annual subscription",
             "benefit": "Complimentary food/drink items or % off at participating restaurants — visible inside the Zomato app"},
        ],
        "expected_savings": "Pro members typically save AED 1,000–2,500/year on dining.",
    },
    "repeat": {
        "tiers": [
            {"name": "Personalised", "threshold": "Free signup",
             "benefit": "Discount % grows with frequency and spend at each participating venue — no fixed tier ladder"},
        ],
        "expected_savings": "Frequent visitors to a single venue can hit 25%+ effective discount; casual users see 5–10%.",
    },
    "elite_club": {
        "tiers": [
            {"name": "Silver", "threshold": "Paid Silver tier",
             "benefit": "Up to 30% off dining, basic vouchers (welcome drinks, dessert for two)"},
            {"name": "Gold", "threshold": "Paid Gold tier",
             "benefit": "Higher % discounts + dining cash vouchers + lunch/dinner invitations"},
            {"name": "Platinum", "threshold": "Paid Platinum tier",
             "benefit": "Highest % discount + premium voucher library + priority booking"},
        ],
        "expected_savings": "Silver members at 5-star Dubai hotels save AED 2,000–5,000/year on dining alone; Platinum heavy users 10,000+.",
    },
    "supper_club": {
        "tiers": [
            {"name": "Gold", "threshold": "From AED 275/year",
             "benefit": "Access to all 150+ offers; auto bill discount; unlimited reservations"},
            {"name": "Diamond", "threshold": "Higher annual fee",
             "benefit": "Premium offers + priority booking + occasional invitations"},
            {"name": "Platinum", "threshold": "Top tier",
             "benefit": "All perks + exclusive experiences and private events"},
        ],
        "expected_savings": "A monthly diner saves around AED 3,000–6,000/year vs full price.",
    },
    "emirates_platinum": {
        "tiers": [
            {"name": "Emirates Platinum", "threshold": "Free for Emirates Group employees + up to 3 dependants",
             "benefit": "10–30% off dining, retail, leisure across 100+ Dubai venues"},
        ],
        "expected_savings": "Active families typically save AED 4,000–8,000/year across dining and lifestyle spend.",
    },
    "shukran": {
        "tiers": [
            {"name": "Silver", "threshold": "Free signup",
             "benefit": "Earn Shukrans (points) at Centrepoint, Max, Home Centre, Babyshop, Splash and partner brands"},
            {"name": "Gold", "threshold": "Higher annual spend tier",
             "benefit": "Faster point earning + premium events + early access to sales"},
        ],
        "expected_savings": "Households doing major Landmark Group shopping (apparel + home + kids) can earn back 3–5% in Shukrans.",
    },
    "share_rewards": {
        "tiers": [
            {"name": "Member", "threshold": "Free signup",
             "benefit": "Earn 2.5–150 SHARE points per AED 100 at MAF brands (Carrefour, Mall of the Emirates, City Centre, VOX, Magic Planet, Ski Dubai, LEGO, Crate & Barrel, etc.)"},
        ],
        "expected_savings": "Frequent Carrefour shoppers earn back ~2–5% as redeemable points; bigger gains on entertainment + dining at MAF malls.",
    },
    "emirates_skywards": {
        "tiers": [
            {"name": "Blue", "threshold": "Free signup",
             "benefit": "Earn miles on flights, partners and 400+ UAE retail/dining brands via Skywards Everyday"},
            {"name": "Silver", "threshold": "25,000 tier miles or 25 flights/year",
             "benefit": "Lounge access, priority boarding, extra baggage, 25% bonus miles"},
            {"name": "Gold", "threshold": "50,000 tier miles or 50 flights/year",
             "benefit": "Business class lounge access, priority check-in, 50% bonus miles, dedicated reservation line"},
            {"name": "Platinum", "threshold": "150,000 tier miles or 75+ flights/year",
             "benefit": "First class lounge, dedicated concierge, 75% bonus miles, premium upgrade priority"},
        ],
        "expected_savings": "Casual UAE-only users earn AED 200–500/year via Skywards Everyday partners; frequent flyers unlock vastly more value via miles redemptions.",
    },
    "in_house": {
        "tiers": [
            {"name": "Per-venue", "threshold": "Varies by brand",
             "benefit": "Each venue's own loyalty program — typically points-based with free items, tier perks, or signup credit. Open the venue's tile to see specifics."},
        ],
        "expected_savings": "Effective rebate varies by brand; coffee shops 8–15%, restaurant chains 5–10%, hotels 5–8%.",
    },
}


def seed_and_backfill(apps, schema_editor):
    Program = apps.get_model("discounts", "Program")

    # Insert / update the three new programs.
    for spec in NEW_PROGRAMS:
        Program.objects.update_or_create(
            slug=spec["slug"],
            defaults={k: v for k, v in spec.items() if k != "slug"},
        )

    # Backfill tier info on existing programs (only update those two fields,
    # leave name/description etc. alone).
    for slug, payload in EXISTING_PROGRAM_TIERS.items():
        Program.objects.filter(slug=slug).update(
            tiers=payload["tiers"],
            expected_savings=payload["expected_savings"],
        )


def reverse(apps, schema_editor):
    """Drop the three new programs and clear backfilled tier fields."""
    Program = apps.get_model("discounts", "Program")
    Program.objects.filter(slug__in=[p["slug"] for p in NEW_PROGRAMS]).delete()
    Program.objects.filter(slug__in=list(EXISTING_PROGRAM_TIERS.keys())).update(
        tiers=[], expected_savings="",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0019_add_program_tiers_and_three_more_programs"),
    ]

    operations = [
        migrations.RunPython(seed_and_backfill, reverse),
    ]
