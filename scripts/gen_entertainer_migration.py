"""Generate apps/discounts/migrations/0015_add_entertainer_venues.py from
the parsed Entertainer Dubai data."""
import json
import os
from pathlib import Path

TMP = Path(os.environ.get("TEMP", "/tmp"))
SRC = TMP / "ent-parsed.json"
DEST = Path("apps/discounts/migrations/0015_add_entertainer_venues.py")


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


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    places = data["places"]
    discounts = data["discounts"]

    body = f'''"""Add Dubai outlets from The Entertainer's merchant sitemap.

Source: theentertainerme.com/site-map/merchants.xml filtered to URLs
containing Dubai-related keywords, deduped to one merchant per slug,
then each outlet's og:title parsed for the venue + area. Each gets one
Discount tagged source_program="entertainer" with discount_type="bogo"
(every Entertainer offer is buy-one-get-one-free).

After creating the rows the migration also runs the same hotel-keyword
website backfill from 0014 and the same experience-keyword auto-tag
from places/0004 — so the new venues get a brand logo (via Clearbit)
and experience filter tags out of the box. The keyword maps are
duplicated here intentionally; future program-import migrations can
copy the same block.

Idempotent: get_or_create on Place (preserves existing rows),
update_or_create on Discount, only-fill-when-empty for website +
experiences.

Reverse drops only the rows added here (matched by slug).
"""

from django.db import migrations


PLACES = {py_repr_list(places, 0)}


DISCOUNTS = {py_repr_list(discounts, 0)}


# Same hotel-keyword map as discounts/0014_backfill_place_websites.
HOTEL_KEYWORDS = [
    ("jw marriott", "marriott.com"),
    ("marriott marquis", "marriott.com"),
    ("ritz-carlton", "ritzcarlton.com"),
    ("ritz carlton", "ritzcarlton.com"),
    ("st. regis", "marriott.com"),
    ("st regis", "marriott.com"),
    ("le méridien", "marriott.com"),
    ("le meridien", "marriott.com"),
    ("waldorf astoria", "hilton.com"),
    ("doubletree", "hilton.com"),
    ("crowne plaza", "ihg.com"),
    ("holiday inn", "ihg.com"),
    ("intercontinental", "ihg.com"),
    ("nh collection", "nh-collection.com"),
    ("one&only", "oneandonlyresorts.com"),
    ("one and only", "oneandonlyresorts.com"),
    ("royal mirage", "oneandonlyresorts.com"),
    ("banyan tree", "banyantree.com"),
    ("burj al arab", "jumeirah.com"),
    ("madinat jumeirah", "jumeirah.com"),
    ("madinat", "jumeirah.com"),
    ("al qasr", "jumeirah.com"),
    ("mina a salam", "jumeirah.com"),
    ("dukes", "dukesthepalm.com"),
    ("dusit thani", "dusit.com"),
    ("dusit", "dusit.com"),
    ("anantara", "anantara.com"),
    ("avani", "avanihotels.com"),
    ("lapita", "marriott.com"),
    ("rixos", "rixos.com"),
    ("kempinski", "kempinski.com"),
    ("al habtoor", "habtoorhotels.com"),
    ("habtoor", "habtoorhotels.com"),
    ("rove", "rovehotels.com"),
    ("citymax", "citymaxhotels.com"),
    ("address", "addresshotels.com"),
    ("vida", "vidahotels.com"),
    ("palazzo versace", "palazzoversace.ae"),
    ("bvlgari", "bulgarihotels.com"),
    ("mandarin oriental", "mandarinoriental.com"),
    ("four seasons", "fourseasons.com"),
    ("th8", "th8palm.com"),
    ("five jumeirah village", "fivehotelsandresorts.com"),
    ("five palm jumeirah", "fivehotelsandresorts.com"),
    ("five luxe", "fivehotelsandresorts.com"),
    ("conrad", "hilton.com"),
    ("hilton", "hilton.com"),
    ("hyatt", "hyatt.com"),
    ("sofitel", "sofitel.com"),
    ("fairmont", "fairmont.com"),
    ("raffles", "raffles.com"),
    ("movenpick", "movenpick.com"),
    ("mövenpick", "movenpick.com"),
    ("novotel", "novotel.com"),
    ("pullman", "pullman.com"),
    ("swissotel", "swissotel.com"),
    ("voco", "ihg.com"),
    ("kimpton", "ihg.com"),
    ("sheraton", "marriott.com"),
    ("renaissance hotel", "marriott.com"),
    ("westin", "marriott.com"),
    ("marriott", "marriott.com"),
    ("rotana", "rotana.com"),
    ("millennium", "millenniumhotels.com"),
    ("shangri-la", "shangri-la.com"),
    ("shangri la", "shangri-la.com"),
    ("atlantis", "atlantis.com"),
    ("jumeirah", "jumeirah.com"),
    ("aloft", "marriott.com"),
    ("ja hatta", "jaresorts.com"),
    ("centara", "centarahotelsresorts.com"),
    ("me dubai", "melia.com"),
    ("melia", "melia.com"),
    ("the h dubai", "h-hotel.com"),
    ("mileo", "mileohotelthepalm.com"),
    ("wafi", "wafi.com"),
    ("townsquare", "townsquaredubai.com"),
    ("coya", "coyarestaurant.com"),
    ("99 sushi", "99sushibar.com"),
    ("la serre", "laserre.ae"),
    ("gerbou", "gerbou.ae"),
    ("duck & waffle", "duckandwaffle.com"),
    ("duck and waffle", "duckandwaffle.com"),
    ("la perle", "laperle.com"),
    ("nikki beach", "nikkibeach.com"),
    ("lila molino", "lilamolino.com"),
    ("trader vic", "tradervics.com"),
    ("kanpai", "kanpai.ae"),
]

# Same experience map as places/0004_seed_experiences_and_autotag.
EXPERIENCE_KEYWORDS = {{
    "breakfast":     ["breakfast"],
    "brunch":        ["brunch"],
    "lunch":         ["lunch", "business lunch"],
    "dinner":        ["dinner", "dinner buffet", "à la carte"],
    "afternoon-tea": ["afternoon tea", "high tea"],
    "drinks":        ["cocktail", "wine", "bubbly", "bar ", " bar,", "drinks"],
    "coffee":        ["coffee", "barista", "cafe ", "café "],
    "pool":          ["pool", "skypool", "pool club", "pool access"],
    "beach":         ["beach", "beach club"],
    "spa":           ["spa", "wellness", "massage", "facial"],
    "staycation":    ["staycation", "overnight", "hour stay", "hour staycation", "night stay"],
}}


def add_entertainer(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")
    Experience = apps.get_model("places", "Experience")

    place_by_slug = {{}}
    for spec in PLACES:
        place, _ = Place.objects.get_or_create(
            slug=spec["slug"],
            defaults={{
                "name": spec["name"],
                "category": "restaurant",  # Entertainer is mostly food/drink
                "area": spec["area"],
                "address": "",
                "phone": "",
                "website": "",  # filled by hotel-keyword backfill below
                "description": (
                    f'{{spec["name"]}} — Dubai outlet listed on The '
                    f'Entertainer. Buy-one-get-one-free offers; details '
                    f'on theentertainerme.com.'
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
                "discount_type": "bogo",
                "source_program": "entertainer",
                "description": (
                    "Buy-one-get-one-free offers for Entertainer "
                    "subscribers. Open the Entertainer app to view current "
                    "redemptions and book."
                ),
                "terms": (
                    "Subject to Entertainer's terms. Offer availability "
                    "may change; confirm in the Entertainer app before "
                    "visiting."
                ),
                "external_url": d["external_url"],
                "is_active": True,
                "is_featured": False,
            }},
        )

    # Backfill website on all websiteless places (only the new ones,
    # since older places already got 0014's pass).
    for p in Place.objects.filter(website=""):
        haystack = " ".join([p.name or "", p.area or "", p.address or ""]).lower()
        for keyword, domain in HOTEL_KEYWORDS:
            if keyword in haystack:
                Place.objects.filter(pk=p.pk).update(website=f"https://www.{{domain}}/")
                break

    # Auto-tag experiences on places without any experience yet.
    by_slug = {{e.slug: e for e in Experience.objects.all()}}
    for p in Place.objects.filter(experiences__isnull=True).iterator():
        titles_blob = " ".join(
            Discount.objects.filter(place=p).values_list("title", flat=True)
        ).lower()
        titles_blob += " " + (p.name or "").lower() + " " + (p.description or "").lower()
        if not titles_blob.strip():
            continue
        for tag_slug, phrases in EXPERIENCE_KEYWORDS.items():
            if tag_slug not in by_slug:
                continue
            for phrase in phrases:
                if phrase in titles_blob:
                    p.experiences.add(by_slug[tag_slug])
                    break


def remove_entertainer(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")
    Discount.objects.filter(slug__in=[d["discount_slug"] for d in DISCOUNTS]).delete()
    Place.objects.filter(slug__in=[p["slug"] for p in PLACES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0014_backfill_place_websites"),
        ("places", "0004_seed_experiences_and_autotag"),
    ]

    operations = [
        migrations.RunPython(add_entertainer, remove_entertainer),
    ]
'''

    DEST.write_text(body, encoding="utf-8")
    print(f"wrote {DEST} ({len(places)} places, {len(discounts)} discounts)")


if __name__ == "__main__":
    main()
