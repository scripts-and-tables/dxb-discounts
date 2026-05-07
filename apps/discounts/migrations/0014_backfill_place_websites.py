"""Backfill `Place.website` for the ~148 Supper Club venues that were
imported without one. The site uses `place.website` to derive a Clearbit
brand-logo URL via `Place.logo_url`, so a websiteless place renders no
logo at all.

Strategy: scan each Place's area + address + name for known hotel-chain
keywords (most Supper Club venues are restaurants/pools inside major
hotels). Assign the corresponding chain domain. Clearbit then serves the
chain's logo for every venue inside that hotel — close enough that the
home tile and place page no longer look empty.

Standalone restaurants without a recognisable chain keyword stay
websiteless and can be filled in via /admin/ later. Idempotent: only
updates rows where website is currently empty.
"""
from django.db import migrations


# Order matters: longer / more specific keywords first so e.g.
# "ritz-carlton" wins over a hypothetical "ritz" prefix on something
# unrelated. Standardised on lowercase; the keyword check normalises
# the haystack to lowercase too.
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
    ("address ", "addresshotels.com"),
    ("vida ", "vidahotels.com"),
    ("palazzo versace", "palazzoversace.ae"),
    ("bvlgari", "bulgarihotels.com"),
    ("mandarin oriental", "mandarinoriental.com"),
    ("four seasons", "fourseasons.com"),
    ("emirates palace", "mandarinoriental.com"),
    ("zaya nurai", "zayanurai.com"),
    ("atlantis the royal", "atlantis.com"),
    ("th8 the palm", "th8palm.com"),
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
    # Second sweep — chains and brands found in remaining rows
    ("ja hatta", "jaresorts.com"),
    ("ja resort", "jaresorts.com"),
    ("aloft", "marriott.com"),
    ("ac hotel", "marriott.com"),
    ("centara", "centarahotelsresorts.com"),
    ("me dubai", "melia.com"),
    ("melia", "melia.com"),
    ("the h dubai", "h-hotel.com"),
    ("the h ", "h-hotel.com"),
    ("the h,", "h-hotel.com"),
    ("mileo", "mileohotelthepalm.com"),
    ("wafi", "wafi.com"),
    ("townsquare", "townsquaredubai.com"),
    # Independent restaurants with their own brand sites
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


def backfill_websites(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    for p in Place.objects.filter(website=""):
        haystack = " ".join([p.name or "", p.area or "", p.address or ""]).lower()
        for keyword, domain in HOTEL_KEYWORDS:
            if keyword in haystack:
                Place.objects.filter(pk=p.pk).update(website=f"https://www.{domain}/")
                break


def clear_backfilled(apps, schema_editor):
    """Reverse: clear websites that match exactly the URLs we'd set forward.
    Leaves any manually-entered website alone."""
    Place = apps.get_model("places", "Place")
    forward_urls = {f"https://www.{d}/" for _, d in HOTEL_KEYWORDS}
    Place.objects.filter(website__in=forward_urls).update(website="")


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0013_fix_misparsed_supper_club_venues"),
    ]

    operations = [
        migrations.RunPython(backfill_websites, clear_backfilled),
    ]
