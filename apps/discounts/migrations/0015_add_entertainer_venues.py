"""Add Dubai outlets from The Entertainer's merchant sitemap.

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


PLACES = [
    {
        'slug': 'flooka-dubai',
        'name': 'Flooka',
        'area': 'Jumeirah',
        'url': 'https://www.theentertainerme.com/outlets/flooka-dubai/detail',
    },
    {
        'slug': 'benjarong-dubai',
        'name': 'Benjarong Dubai',
        'area': 'SZR - Sheikh Zayed Road',
        'url': 'https://www.theentertainerme.com/outlets/benjarong-dubai/detail',
    },
    {
        'slug': 'royal-orchid-dubai',
        'name': 'Royal Orchid',
        'area': 'Downtown Dubai',
        'url': 'https://www.theentertainerme.com/outlets/royal-orchid-dubai/detail',
    },
    {
        'slug': 'trader-vics-souk-madinat-jumeirah',
        'name': "Trader Vic's - Souk Madinat Jumeirah",
        'area': 'Al Sufouh',
        'url': 'https://www.theentertainerme.com/outlets/trader-vics-souk-madinat-jumeirah/detail',
    },
    {
        'slug': 'oceana-dubai',
        'name': 'Oceana Kitchen',
        'area': 'JBR - Jumeirah Beach Residence',
        'url': 'https://www.theentertainerme.com/outlets/oceana-dubai/detail',
    },
    {
        'slug': 'haagen-dazs-dubai',
        'name': 'Haagen-Dazs Dubai',
        'area': 'Downtown Dubai',
        'url': 'https://www.theentertainerme.com/outlets/haagen-dazs-dubai/detail',
    },
    {
        'slug': 'the-pizza-company-dubai',
        'name': 'The Pizza Company',
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/the-pizza-company-dubai/detail',
    },
    {
        'slug': 'caffe-divino-dubai',
        'name': 'Caffe Divino',
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/caffe-divino-dubai/detail',
    },
    {
        'slug': 'dubai-dolphinarium',
        'name': 'Dubai Dolphinarium',
        'area': 'Umm Hurair',
        'url': 'https://www.theentertainerme.com/outlets/dubai-dolphinarium/detail',
    },
    {
        'slug': 'jones-the-grocer-dubai',
        'name': 'Jones the Grocer',
        'area': 'SZR - Sheikh Zayed Road',
        'url': 'https://www.theentertainerme.com/outlets/jones-the-grocer-dubai/detail',
    },
    {
        'slug': 'tour-dubai-dhow-dinner-cruise',
        'name': 'Tour Dubai - Dhow Cruise',
        'area': 'Al Jaddaf',
        'url': 'https://www.theentertainerme.com/outlets/tour-dubai-dhow-dinner-cruise/detail',
    },
    {
        'slug': 'dubai-ice-rink',
        'name': 'Dubai Ice Rink',
        'area': 'Downtown Dubai',
        'url': 'https://www.theentertainerme.com/outlets/dubai-ice-rink/detail',
    },
    {
        'slug': 'fun-city-dubai',
        'name': 'Fun City',
        'area': 'Al Mizhar',
        'url': 'https://www.theentertainerme.com/outlets/fun-city-dubai/detail',
    },
    {
        'slug': 'hard-rock-cafe-dubai',
        'name': 'Hard Rock Cafe',
        'area': 'Ras Al Khor',
        'url': 'https://www.theentertainerme.com/outlets/hard-rock-cafe-dubai/detail',
    },
    {
        'slug': 'butcher-shop-grill-dubai',
        'name': 'Butcher Shop & Grill',
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/butcher-shop-grill-dubai/detail',
    },
    {
        'slug': 'surf-house-dubai',
        'name': 'Surf House Dubai',
        'area': 'Umm Suqeim',
        'url': 'https://www.theentertainerme.com/outlets/surf-house-dubai/detail',
    },
    {
        'slug': 'tgi-fridays-dubai',
        'name': 'TGI Fridays',
        'area': 'Jumeirah',
        'url': 'https://www.theentertainerme.com/outlets/tgi-fridays-dubai/detail',
    },
    {
        'slug': 'adventure-zone-by-adventure-hq-dubai',
        'name': 'Adventure Zone by Adventure HQ',
        'area': 'Al Quoz',
        'url': 'https://www.theentertainerme.com/outlets/adventure-zone-by-adventure-hq-dubai/detail',
    },
    {
        'slug': 'dominos-pizza-dubai',
        'name': "Domino's Pizza",
        'area': 'Al Barsha',
        'url': 'https://www.theentertainerme.com/outlets/dominos-pizza-dubai/detail',
    },
    {
        'slug': 'texas-chicken-dubai',
        'name': 'Texas Chicken',
        'area': 'Bur Dubai',
        'url': 'https://www.theentertainerme.com/outlets/texas-chicken-dubai/detail',
    },
    {
        'slug': 'nandos-dubai',
        'name': "Nando's",
        'area': 'Downtown Dubai',
        'url': 'https://www.theentertainerme.com/outlets/nandos-dubai/detail',
    },
    {
        'slug': 'zafran-dubai',
        'name': 'Zafran',
        'area': 'Mirdif',
        'url': 'https://www.theentertainerme.com/outlets/zafran-dubai/detail',
    },
    {
        'slug': 'tamani-marina-hotel-and-hotel-apartment',
        'name': 'Tamani Marina Hotel and Hotel Apartment',
        'area': 'Dubai Marina',
        'url': 'https://www.theentertainerme.com/outlets/tamani-marina-hotel-and-hotel-apartment/detail',
    },
    {
        'slug': 'dubai-autodrome',
        'name': 'Dubai Autodrome',
        'area': 'Dubai Motor City',
        'url': 'https://www.theentertainerme.com/outlets/dubai-autodrome/detail',
    },
    {
        'slug': 'carluccios-dubai',
        'name': "Carluccio's",
        'area': 'Downtown Dubai',
        'url': 'https://www.theentertainerme.com/outlets/carluccios-dubai/detail',
    },
    {
        'slug': 'burger-king-dubai',
        'name': 'Burger King',
        'area': 'Al Quoz',
        'url': 'https://www.theentertainerme.com/outlets/burger-king-dubai/detail',
    },
    {
        'slug': 'tim-hortons-dubai',
        'name': 'Tim Hortons',
        'area': 'Dubai World Trade Centre',
        'url': 'https://www.theentertainerme.com/outlets/tim-hortons-dubai/detail',
    },
    {
        'slug': 'dunkin-dubai',
        'name': "Dunkin'",
        'area': 'DSO - Dubai Silicon Oasis',
        'url': 'https://www.theentertainerme.com/outlets/dunkin-dubai/detail',
    },
    {
        'slug': 'the-yellow-boats-dubai',
        'name': 'The Yellow Boats',
        'area': 'Dubai Marina',
        'url': 'https://www.theentertainerme.com/outlets/the-yellow-boats-dubai/detail',
    },
    {
        'slug': 'cold-stone-creamery-dubai',
        'name': 'Cold Stone Creamery Dubai',
        'area': 'SZR - Sheikh Zayed Road',
        'url': 'https://www.theentertainerme.com/outlets/cold-stone-creamery-dubai/detail',
    },
    {
        'slug': 'hair-works-beauty-dubai',
        'name': 'Hair Works Beauty',
        'area': 'Umm Suqeim',
        'url': 'https://www.theentertainerme.com/outlets/hair-works-beauty-dubai/detail',
    },
    {
        'slug': 'the-spa-hilton-jbr',
        'name': 'The Spa - Hilton JBR',
        'area': 'JBR - Jumeirah Beach Residence',
        'url': 'https://www.theentertainerme.com/outlets/the-spa-hilton-jbr/detail',
    },
    {
        'slug': 'buffalo-wings-rings-dubai',
        'name': 'Buffalo Wings & Rings',
        'area': 'DIFC - Dubai International Financial Center',
        'url': 'https://www.theentertainerme.com/outlets/buffalo-wings-rings-dubai/detail',
    },
    {
        'slug': 'sofitel-spa-dubai-downtown',
        'name': 'Sofitel SPA Dubai Downtown',
        'area': 'Downtown Dubai',
        'url': 'https://www.theentertainerme.com/outlets/sofitel-spa-dubai-downtown/detail',
    },
    {
        'slug': 'vivaldi-restaurant-dubai',
        'name': 'Vivaldi Restaurant',
        'area': 'Dubai Creek',
        'url': 'https://www.theentertainerme.com/outlets/vivaldi-restaurant-dubai/detail',
    },
    {
        'slug': 'la-brioche-dubai',
        'name': 'La Brioche',
        'area': 'Mirdif',
        'url': 'https://www.theentertainerme.com/outlets/la-brioche-dubai/detail',
    },
    {
        'slug': 'shang-palace-at-shangri-la-dubai',
        'name': 'Shang Palace at Shangri-La Dubai',
        'area': 'SZR - Sheikh Zayed Road',
        'url': 'https://www.theentertainerme.com/outlets/shang-palace-at-shangri-la-dubai/detail',
    },
    {
        'slug': 'tony-romas-dubai',
        'name': "Tony Roma's",
        'area': 'SZR - Sheikh Zayed Road',
        'url': 'https://www.theentertainerme.com/outlets/tony-romas-dubai/detail',
    },
    {
        'slug': 'papa-johns-pizza-dubai',
        'name': 'Papa Johns Pizza',
        'area': 'Al Barsha',
        'url': 'https://www.theentertainerme.com/outlets/papa-johns-pizza-dubai/detail',
    },
    {
        'slug': 'escape-hunt-dubai',
        'name': 'Escape Hunt',
        'area': 'Jumeirah',
        'url': 'https://www.theentertainerme.com/outlets/escape-hunt-dubai/detail',
    },
    {
        'slug': 'fun-block-dubai',
        'name': 'Fun Block',
        'area': 'Fujairah',
        'url': 'https://www.theentertainerme.com/outlets/fun-block-dubai/detail',
    },
    {
        'slug': 'belgian-beer-caf-madinat-jumeirah',
        'name': 'Belgian Beer Cafe Madinat Jumeirah',
        'area': 'Al Sufouh',
        'url': 'https://www.theentertainerme.com/outlets/belgian-beer-caf-madinat-jumeirah/detail',
    },
    {
        'slug': 'ctaste-centro-al-barsha',
        'name': 'c.taste - Centro Barsha',
        'area': 'Al Barsha',
        'url': 'https://www.theentertainerme.com/outlets/ctaste-centro-al-barsha/detail',
    },
    {
        'slug': 'wyndham-dubai-marina',
        'name': 'The First Collection Marina',
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/wyndham-dubai-marina/detail',
    },
    {
        'slug': 'dennys-dubai',
        'name': "Denny's",
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/dennys-dubai/detail',
    },
    {
        'slug': 'the-rose-crown-dubai',
        'name': 'The Rose & Crown Dubai',
        'area': 'SZR - Sheikh Zayed Road',
        'url': 'https://www.theentertainerme.com/outlets/the-rose-crown-dubai/detail',
    },
    {
        'slug': 'chloes-beauty-hair-nails-dubai',
        'name': "Chloe's Beauty, Hair & Nails",
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/chloes-beauty-hair-nails-dubai/detail',
    },
    {
        'slug': 'metropolitan-hotel-dubai',
        'name': 'Metropolitan Hotel Dubai',
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/metropolitan-hotel-dubai/detail',
    },
    {
        'slug': 'soul-senses-spa-wellness-dubai',
        'name': 'Soul Senses Spa & Wellness Standard - Dubai',
        'area': 'Al Barsha',
        'url': 'https://www.theentertainerme.com/outlets/soul-senses-spa-wellness-dubai/detail',
    },
    {
        'slug': 'lucky-voice-dubai',
        'name': 'Lucky Voice Dubai',
        'area': 'Barsha Heights',
        'url': 'https://www.theentertainerme.com/outlets/lucky-voice-dubai/detail',
    },
    {
        'slug': 'doner-gyros-dubai',
        'name': 'Doner & Gyros Dubai',
        'area': 'Dubai Marina',
        'url': 'https://www.theentertainerme.com/outlets/doner-gyros-dubai/detail',
    },
    {
        'slug': 'champion-cleaners-dubai',
        'name': 'Champion Cleaners',
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/champion-cleaners-dubai/detail',
    },
    {
        'slug': 'tryp-by-wyndham-dubai',
        'name': 'TRYP by Wyndham Dubai',
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/tryp-by-wyndham-dubai/detail',
    },
    {
        'slug': 'lock-stock-barrel-jbr',
        'name': 'Lock Stock & Barrel',
        'area': 'JBR - Jumeirah Beach Residence',
        'url': 'https://www.theentertainerme.com/outlets/lock-stock-barrel-jbr/detail',
    },
    {
        'slug': 'belgian-beer-cafe-dubai',
        'name': 'Belgian Beer Cafe',
        'area': 'Barsha Heights',
        'url': 'https://www.theentertainerme.com/outlets/belgian-beer-cafe-dubai/detail',
    },
    {
        'slug': 'park-inn-by-radisson-dubai-motor-city',
        'name': 'Park Inn by Radisson, Dubai Motor City',
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/park-inn-by-radisson-dubai-motor-city/detail',
    },
    {
        'slug': 'grand-hyatt-dubai',
        'name': 'Grand Hyatt Dubai',
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/grand-hyatt-dubai/detail',
    },
    {
        'slug': 'dunes-cafe-at-shangri-la-dubai',
        'name': 'Dunes Cafe at Shangri-La Dubai',
        'area': 'SZR - Sheikh Zayed Road',
        'url': 'https://www.theentertainerme.com/outlets/dunes-cafe-at-shangri-la-dubai/detail',
    },
    {
        'slug': 'off-the-hook-dubai',
        'name': 'Off The HOOK',
        'area': 'Deira',
        'url': 'https://www.theentertainerme.com/outlets/off-the-hook-dubai/detail',
    },
    {
        'slug': 'radisson-blu-hotel-dubai-waterfront',
        'name': 'Radisson Blu Hotel, Dubai Waterfront',
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/radisson-blu-hotel-dubai-waterfront/detail',
    },
    {
        'slug': 'the-larder-radisson-blu-hotel-dubai-waterfront',
        'name': 'The Larder - Radisson Blu Hotel, Dubai Waterfront',
        'area': 'Business Bay',
        'url': 'https://www.theentertainerme.com/outlets/the-larder-radisson-blu-hotel-dubai-waterfront/detail',
    },
    {
        'slug': 'trader-vics-hilton-dubai-jumeirah',
        'name': "Trader Vic's - JBR",
        'area': 'JBR - Jumeirah Beach Residence',
        'url': 'https://www.theentertainerme.com/outlets/trader-vics-hilton-dubai-jumeirah/detail',
    },
    {
        'slug': 'esthetic-sense-dubai',
        'name': 'Esthetic Sense Dubai',
        'area': 'The Palm Jumeirah',
        'url': 'https://www.theentertainerme.com/outlets/esthetic-sense-dubai/detail',
    },
    {
        'slug': 'cafe-bateel-dubai',
        'name': 'Cafe Bateel - Dubai',
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/cafe-bateel-dubai/detail',
    },
    {
        'slug': 'pizza-di-rocco-dubai',
        'name': 'Pizza Di Rocco',
        'area': 'JLT - Jumeirah Lake Towers',
        'url': 'https://www.theentertainerme.com/outlets/pizza-di-rocco-dubai/detail',
    },
    {
        'slug': 'the-lounge-dubai',
        'name': 'The Lounge',
        'area': 'Deira',
        'url': 'https://www.theentertainerme.com/outlets/the-lounge-dubai/detail',
    },
    {
        'slug': 'famous-daves-dubai',
        'name': "Famous Dave's - Dubai",
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/famous-daves-dubai/detail',
    },
    {
        'slug': 'tepfactor-dubai',
        'name': 'TEPfactor',
        'area': 'JBR - Jumeirah Beach Residence',
        'url': 'https://www.theentertainerme.com/outlets/tepfactor-dubai/detail',
    },
    {
        'slug': 'the-pizza-pie-factory-dubai',
        'name': 'The Pizza Pie Factory',
        'area': 'Jumeirah',
        'url': 'https://www.theentertainerme.com/outlets/the-pizza-pie-factory-dubai/detail',
    },
    {
        'slug': 'focus-restaurant-hyatt-place-dubai-wasl-district',
        'name': 'Focus Restaurant - Hyatt Place Dubai Wasl District',
        'area': 'Naif',
        'url': 'https://www.theentertainerme.com/outlets/focus-restaurant-hyatt-place-dubai-wasl-district/detail',
    },
    {
        'slug': 'dubai-explorers',
        'name': 'Dubai Explorers',
        'area': 'Barsha Heights',
        'url': 'https://www.theentertainerme.com/outlets/dubai-explorers/detail',
    },
    {
        'slug': 'trampo-extreme-dubai-mall',
        'name': 'TRAMPO',
        'area': 'Downtown Dubai',
        'url': 'https://www.theentertainerme.com/outlets/trampo-extreme-dubai-mall/detail',
    },
    {
        'slug': 'focus-bar-jumeirah',
        'name': 'Focus Bar - Jumeirah',
        'area': 'Al Mina',
        'url': 'https://www.theentertainerme.com/outlets/focus-bar-jumeirah/detail',
    },
    {
        'slug': 'poke-co-dubai',
        'name': 'Poke & Co.',
        'area': 'DIFC - Dubai International Financial Center',
        'url': 'https://www.theentertainerme.com/outlets/poke-co-dubai/detail',
    },
    {
        'slug': 'focus-restaurant-jumeirah',
        'name': 'Focus Restaurant - Jumeirah',
        'area': 'Al Mina',
        'url': 'https://www.theentertainerme.com/outlets/focus-restaurant-jumeirah/detail',
    },
    {
        'slug': 'bab-al-qasr-hotel-pool',
        'name': 'Bab Al Qasr Hotel Pool & Beach',
        'area': 'Al Khubeirah',
        'url': 'https://www.theentertainerme.com/outlets/bab-al-qasr-hotel-pool/detail',
    },
    {
        'slug': 'the-larder-radisson-blu-hotel-dubai-canal-view',
        'name': 'The Larder - Radisson Blu Hotel, Dubai Canal View',
        'area': 'SZR - Sheikh Zayed Road',
        'url': 'https://www.theentertainerme.com/outlets/the-larder-radisson-blu-hotel-dubai-canal-view/detail',
    },
    {
        'slug': 'molten-chocolate-cafe-dubai',
        'name': 'Molten Chocolate Cafe',
        'area': 'Sharjah',
        'url': 'https://www.theentertainerme.com/outlets/molten-chocolate-cafe-dubai/detail',
    },
    {
        'slug': 'beyond-pancakes-marina-square',
        'name': 'Beyond Pancakes Marina Square',
        'area': 'Marina Bay',
        'url': 'https://www.theentertainerme.com/outlets/beyond-pancakes-marina-square/detail',
    },
    {
        'slug': 'wox-hyatt-place-dubai-jumeirah',
        'name': 'Wox - Hyatt Place Dubai Jumeirah',
        'area': 'Al Mina',
        'url': 'https://www.theentertainerme.com/outlets/wox-hyatt-place-dubai-jumeirah/detail',
    },
    {
        'slug': 'radisson-blu-hotel-dubai-canal-view',
        'name': 'Radisson Blu Hotel, Dubai Canal View',
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/radisson-blu-hotel-dubai-canal-view/detail',
    },
    {
        'slug': 'harrys-marina-bay',
        'name': "Harry's Marina Bay",
        'area': 'Marina Bay',
        'url': 'https://www.theentertainerme.com/outlets/harrys-marina-bay/detail',
    },
    {
        'slug': 'ginos-deli-dubai',
        'name': "Gino's Deli",
        'area': 'JLT - Jumeirah Lake Towers',
        'url': 'https://www.theentertainerme.com/outlets/ginos-deli-dubai/detail',
    },
    {
        'slug': 'taj-dubai',
        'name': 'Taj Dubai',
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/taj-dubai/detail',
    },
    {
        'slug': 'andaz-dubai-the-palm',
        'name': 'Hyatt Andaz Dubai The Palm',
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/andaz-dubai-the-palm/detail',
    },
    {
        'slug': 'kimura-ya-authentic-japanese-restaurant-anantara-downtown-dubai-hotel',
        'name': 'Kimura-ya Authentic Japanese Restaurant',
        'area': 'Downtown Dubai',
        'url': 'https://www.theentertainerme.com/outlets/kimura-ya-authentic-japanese-restaurant-anantara-downtown-dubai-hotel/detail',
    },
    {
        'slug': 'dubai-dream-casters',
        'name': 'Dubai Dream Casters',
        'area': 'Dubai Marina',
        'url': 'https://www.theentertainerme.com/outlets/dubai-dream-casters/detail',
    },
    {
        'slug': 'staybridge-suites-dubai-al-maktoum-airport',
        'name': 'Staybridge Suites Dubai Al-Maktoum Airport',
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/staybridge-suites-dubai-al-maktoum-airport/detail',
    },
    {
        'slug': 'holiday-inn-dubai-al-maktoum-airport',
        'name': 'Holiday Inn Dubai Al-Maktoum Airport',
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/holiday-inn-dubai-al-maktoum-airport/detail',
    },
    {
        'slug': 'the-pool-at-doubletree-by-hilton-hotel-dubai-jumeirah-beach',
        'name': 'DoubleTree by Hilton JBR - Pool & Beach',
        'area': 'JBR - Jumeirah Beach Residence',
        'url': 'https://www.theentertainerme.com/outlets/the-pool-at-doubletree-by-hilton-hotel-dubai-jumeirah-beach/detail',
    },
    {
        'slug': 'explorers-dubai',
        'name': 'Explorers Dubai',
        'area': 'Al Barsha',
        'url': 'https://www.theentertainerme.com/outlets/explorers-dubai/detail',
    },
    {
        'slug': 'hurricanes-grill-dubai-mall',
        'name': "Hurricane's Grill",
        'area': 'Downtown Dubai',
        'url': 'https://www.theentertainerme.com/outlets/hurricanes-grill-dubai-mall/detail',
    },
    {
        'slug': 'dubai-adventures',
        'name': 'Dubai Adventures',
        'area': 'JLT - Jumeirah Lake Towers',
        'url': 'https://www.theentertainerme.com/outlets/dubai-adventures/detail',
    },
    {
        'slug': 'carnival-by-tresind-dubai',
        'name': 'Carnival by Tresind',
        'area': 'DIFC - Dubai International Financial Center',
        'url': 'https://www.theentertainerme.com/outlets/carnival-by-tresind-dubai/detail',
    },
    {
        'slug': 'dubai-trip',
        'name': 'Dubai Trip',
        'area': 'Jumeirah',
        'url': 'https://www.theentertainerme.com/outlets/dubai-trip/detail',
    },
    {
        'slug': '800-pizza-authentic-italian-pizza-dubai',
        'name': '800 PIZZA Authentic Italian Pizza',
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/800-pizza-authentic-italian-pizza-dubai/detail',
    },
    {
        'slug': 'dubai-buggy-riders',
        'name': 'Dubai Buggy Riders',
        'area': 'Dubai Marina',
        'url': 'https://www.theentertainerme.com/outlets/dubai-buggy-riders/detail',
    },
    {
        'slug': 'sizzling-wok-dubai',
        'name': 'Sizzling Wok, Business Bay',
        'area': 'Business Bay',
        'url': 'https://www.theentertainerme.com/outlets/sizzling-wok-dubai/detail',
    },
    {
        'slug': 'chicking-dubai',
        'name': 'ChicKing - Dubai',
        'area': 'Al Mamzar',
        'url': 'https://www.theentertainerme.com/outlets/chicking-dubai/detail',
    },
    {
        'slug': 'the-app-tutorial-dubai',
        'name': 'When, Where & How to Use our App',
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/the-app-tutorial-dubai/detail',
    },
    {
        'slug': 'dubai-activities',
        'name': 'Dubai Activities',
        'area': 'Jumeirah',
        'url': 'https://www.theentertainerme.com/outlets/dubai-activities/detail',
    },
    {
        'slug': 'sushi-library-dubai',
        'name': 'Sushi Library',
        'area': 'JLT - Jumeirah Lake Towers',
        'url': 'https://www.theentertainerme.com/outlets/sushi-library-dubai/detail',
    },
    {
        'slug': 'legoland-dubai',
        'name': 'LEGOLAND® Dubai',
        'area': 'Jebel Ali',
        'url': 'https://www.theentertainerme.com/outlets/legoland-dubai/detail',
    },
    {
        'slug': 'motiongate-dubai',
        'name': 'MOTIONGATE™ Dubai',
        'area': 'Jebel Ali',
        'url': 'https://www.theentertainerme.com/outlets/motiongate-dubai/detail',
    },
    {
        'slug': 'the-first-collection-at-jumeirah-village-circle',
        'name': 'The First Collection at Jumeirah Village Circle',
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/the-first-collection-at-jumeirah-village-circle/detail',
    },
    {
        'slug': 'soul-senses-spa-wellness-premium-dubai',
        'name': 'Soul Senses Spa & Wellness Premium - Dubai',
        'area': 'Bur Dubai',
        'url': 'https://www.theentertainerme.com/outlets/soul-senses-spa-wellness-premium-dubai/detail',
    },
    {
        'slug': 'isola-restaurant-dubai',
        'name': 'Isola Restaurant Dubai',
        'area': 'Jumeirah Islands',
        'url': 'https://www.theentertainerme.com/outlets/isola-restaurant-dubai/detail',
    },
    {
        'slug': 'mygolf-dubai',
        'name': 'MyGolf Dubai',
        'area': 'Dubai International City',
        'url': 'https://www.theentertainerme.com/outlets/mygolf-dubai/detail',
    },
    {
        'slug': 'burger-queen-dubai',
        'name': 'Burger 52',
        'area': 'Al Barsha',
        'url': 'https://www.theentertainerme.com/outlets/burger-queen-dubai/detail',
    },
    {
        'slug': 'punjab-grill-dubai',
        'name': 'Punjab Grill',
        'area': 'Downtown Dubai',
        'url': 'https://www.theentertainerme.com/outlets/punjab-grill-dubai/detail',
    },
    {
        'slug': 'aloft-palm-jumeirah-pool-beach',
        'name': 'Aloft Palm Jumeirah - Pool & Beach',
        'area': 'The Palm Jumeirah',
        'url': 'https://www.theentertainerme.com/outlets/aloft-palm-jumeirah-pool-beach/detail',
    },
    {
        'slug': 'the-first-collection-business-bay',
        'name': 'The First Collection Business Bay',
        'area': 'Dubai',
        'url': 'https://www.theentertainerme.com/outlets/the-first-collection-business-bay/detail',
    },
    {
        'slug': 'taj-dubai-gym-and-pool',
        'name': 'Taj Dubai Gym and Pool',
        'area': 'Business Bay',
        'url': 'https://www.theentertainerme.com/outlets/taj-dubai-gym-and-pool/detail',
    },
    {
        'slug': 'lantica-pizzeria-by-michele-dubai-hills-mall',
        'name': "L'Antica Pizzeria by Michele",
        'area': 'Dubai Hills',
        'url': 'https://www.theentertainerme.com/outlets/lantica-pizzeria-by-michele-dubai-hills-mall/detail',
    },
    {
        'slug': 'honest-bowl-dubai',
        'name': 'Honest Bowl',
        'area': 'Al Barsha',
        'url': 'https://www.theentertainerme.com/outlets/honest-bowl-dubai/detail',
    },
    {
        'slug': 'momo-bros-dubai',
        'name': 'Momo Bros',
        'area': 'Business Bay',
        'url': 'https://www.theentertainerme.com/outlets/momo-bros-dubai/detail',
    },
    {
        'slug': 'radisson-red-dubai-silicon-oasis',
        'name': 'Radisson RED Dubai Silicon Oasis',
        'area': 'DSO - Dubai Silicon Oasis',
        'url': 'https://www.theentertainerme.com/outlets/radisson-red-dubai-silicon-oasis/detail',
    },
    {
        'slug': 'madame-tussauds-dubai',
        'name': 'Madame Tussauds Dubai',
        'area': 'Bluewaters Island',
        'url': 'https://www.theentertainerme.com/outlets/madame-tussauds-dubai/detail',
    },
    {
        'slug': 'cosmic-kitchen-al-barsha',
        'name': 'Cosmic Kitchen, Al Barsha',
        'area': 'Al Barsha',
        'url': 'https://www.theentertainerme.com/outlets/cosmic-kitchen-al-barsha/detail',
    },
    {
        'slug': 'maiora-at-nh-collection-dubai-the-palm',
        'name': 'Maiora',
        'area': 'The Palm Jumeirah',
        'url': 'https://www.theentertainerme.com/outlets/maiora-at-nh-collection-dubai-the-palm/detail',
    },
    {
        'slug': 'mandarin-oak-dubai',
        'name': 'Mandarin Oak',
        'area': 'Al Barsha',
        'url': 'https://www.theentertainerme.com/outlets/mandarin-oak-dubai/detail',
    },
    {
        'slug': 'behrouz-biryani-dubai',
        'name': 'Behrouz Biryani',
        'area': 'Al Barsha',
        'url': 'https://www.theentertainerme.com/outlets/behrouz-biryani-dubai/detail',
    },
    {
        'slug': 'fricken-chicken-dubai',
        'name': 'Fricken Chicken',
        'area': 'Al Barsha',
        'url': 'https://www.theentertainerme.com/outlets/fricken-chicken-dubai/detail',
    },
    {
        'slug': 'the-500-calorie-project-dubai',
        'name': 'The 500 Calorie Project',
        'area': 'Al Barsha',
        'url': 'https://www.theentertainerme.com/outlets/the-500-calorie-project-dubai/detail',
    },
    {
        'slug': 'blackout-horror-escape-room-dubai',
        'name': 'Blackout Horror Escape Room',
        'area': 'Al Quoz',
        'url': 'https://www.theentertainerme.com/outlets/blackout-horror-escape-room-dubai/detail',
    },
    {
        'slug': 'desert-rose-tourism-dubai',
        'name': 'Desert Rose Tourism',
        'area': 'Al Karama',
        'url': 'https://www.theentertainerme.com/outlets/desert-rose-tourism-dubai/detail',
    },
    {
        'slug': 'bateel-elan-difc',
        'name': "Bateel El'an - Dubai",
        'area': 'DIFC - Dubai International Financial Center',
        'url': 'https://www.theentertainerme.com/outlets/bateel-elan-difc/detail',
    },
    {
        'slug': 'the-spa-at-intercontinental-dubai-festival-city',
        'name': 'The Spa at InterContinental Dubai Festival City',
        'area': 'DFC - Dubai Festival City',
        'url': 'https://www.theentertainerme.com/outlets/the-spa-at-intercontinental-dubai-festival-city/detail',
    },
    {
        'slug': 'holiday-inn-dubai-business-bay',
        'name': 'Holiday Inn Dubai Business Bay',
        'area': 'Business Bay',
        'url': 'https://www.theentertainerme.com/outlets/holiday-inn-dubai-business-bay/detail',
    },
    {
        'slug': 'dubai-yachts',
        'name': 'Dubai Yachts',
        'area': 'Dubai Marina',
        'url': 'https://www.theentertainerme.com/outlets/dubai-yachts/detail',
    },
    {
        'slug': 'jbr-perk',
        'name': 'JBR Perk',
        'area': 'JBR - Jumeirah Beach Residence',
        'url': 'https://www.theentertainerme.com/outlets/jbr-perk/detail',
    },
    {
        'slug': 'dubai-tourism-and-travel',
        'name': 'Dubai Tourism and Travel',
        'area': 'Downtown Dubai',
        'url': 'https://www.theentertainerme.com/outlets/dubai-tourism-and-travel/detail',
    },
    {
        'slug': 'halo-halo-marina',
        'name': 'Halo Halo - Marina',
        'area': 'Dubai Marina',
        'url': 'https://www.theentertainerme.com/outlets/halo-halo-marina/detail',
    },
    {
        'slug': 'holiday-inn-suites-dubai-science-park',
        'name': 'Holiday Inn & Suites Dubai Science Park',
        'area': 'Al Barsha',
        'url': 'https://www.theentertainerme.com/outlets/holiday-inn-suites-dubai-science-park/detail',
    },
    {
        'slug': 'palazzo-versace-dubai',
        'name': 'Palazzo Versace Dubai',
        'area': 'Al Jaddaf',
        'url': 'https://www.theentertainerme.com/outlets/palazzo-versace-dubai/detail',
    },
    {
        'slug': 'pinsa-romana-dubai',
        'name': 'Pinsa Romana',
        'area': 'JLT - Jumeirah Lake Towers',
        'url': 'https://www.theentertainerme.com/outlets/pinsa-romana-dubai/detail',
    },
    {
        'slug': 'anantara-downtown-dubai-hotel',
        'name': 'Anantara Downtown Dubai Hotel',
        'area': 'Business Bay',
        'url': 'https://www.theentertainerme.com/outlets/anantara-downtown-dubai-hotel/detail',
    },
]


DISCOUNTS = [
    {
        'place_slug': 'flooka-dubai',
        'discount_slug': 'ent-flooka-dubai',
        'title': 'Buy One Get One Free at Flooka via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/flooka-dubai/detail',
    },
    {
        'place_slug': 'benjarong-dubai',
        'discount_slug': 'ent-benjarong-dubai',
        'title': 'Buy One Get One Free at Benjarong Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/benjarong-dubai/detail',
    },
    {
        'place_slug': 'royal-orchid-dubai',
        'discount_slug': 'ent-royal-orchid-dubai',
        'title': 'Buy One Get One Free at Royal Orchid via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/royal-orchid-dubai/detail',
    },
    {
        'place_slug': 'trader-vics-souk-madinat-jumeirah',
        'discount_slug': 'ent-trader-vics-souk-madinat-jumeirah',
        'title': "Buy One Get One Free at Trader Vic's - Souk Madinat Jumeirah via The Entertainer",
        'external_url': 'https://www.theentertainerme.com/outlets/trader-vics-souk-madinat-jumeirah/detail',
    },
    {
        'place_slug': 'oceana-dubai',
        'discount_slug': 'ent-oceana-dubai',
        'title': 'Buy One Get One Free at Oceana Kitchen via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/oceana-dubai/detail',
    },
    {
        'place_slug': 'haagen-dazs-dubai',
        'discount_slug': 'ent-haagen-dazs-dubai',
        'title': 'Buy One Get One Free at Haagen-Dazs Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/haagen-dazs-dubai/detail',
    },
    {
        'place_slug': 'the-pizza-company-dubai',
        'discount_slug': 'ent-the-pizza-company-dubai',
        'title': 'Buy One Get One Free at The Pizza Company via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/the-pizza-company-dubai/detail',
    },
    {
        'place_slug': 'caffe-divino-dubai',
        'discount_slug': 'ent-caffe-divino-dubai',
        'title': 'Buy One Get One Free at Caffe Divino via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/caffe-divino-dubai/detail',
    },
    {
        'place_slug': 'dubai-dolphinarium',
        'discount_slug': 'ent-dubai-dolphinarium',
        'title': 'Buy One Get One Free at Dubai Dolphinarium via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/dubai-dolphinarium/detail',
    },
    {
        'place_slug': 'jones-the-grocer-dubai',
        'discount_slug': 'ent-jones-the-grocer-dubai',
        'title': 'Buy One Get One Free at Jones the Grocer via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/jones-the-grocer-dubai/detail',
    },
    {
        'place_slug': 'tour-dubai-dhow-dinner-cruise',
        'discount_slug': 'ent-tour-dubai-dhow-dinner-cruise',
        'title': 'Buy One Get One Free at Tour Dubai - Dhow Cruise via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/tour-dubai-dhow-dinner-cruise/detail',
    },
    {
        'place_slug': 'dubai-ice-rink',
        'discount_slug': 'ent-dubai-ice-rink',
        'title': 'Buy One Get One Free at Dubai Ice Rink via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/dubai-ice-rink/detail',
    },
    {
        'place_slug': 'fun-city-dubai',
        'discount_slug': 'ent-fun-city-dubai',
        'title': 'Buy One Get One Free at Fun City via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/fun-city-dubai/detail',
    },
    {
        'place_slug': 'hard-rock-cafe-dubai',
        'discount_slug': 'ent-hard-rock-cafe-dubai',
        'title': 'Buy One Get One Free at Hard Rock Cafe via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/hard-rock-cafe-dubai/detail',
    },
    {
        'place_slug': 'butcher-shop-grill-dubai',
        'discount_slug': 'ent-butcher-shop-grill-dubai',
        'title': 'Buy One Get One Free at Butcher Shop & Grill via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/butcher-shop-grill-dubai/detail',
    },
    {
        'place_slug': 'surf-house-dubai',
        'discount_slug': 'ent-surf-house-dubai',
        'title': 'Buy One Get One Free at Surf House Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/surf-house-dubai/detail',
    },
    {
        'place_slug': 'tgi-fridays-dubai',
        'discount_slug': 'ent-tgi-fridays-dubai',
        'title': 'Buy One Get One Free at TGI Fridays via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/tgi-fridays-dubai/detail',
    },
    {
        'place_slug': 'adventure-zone-by-adventure-hq-dubai',
        'discount_slug': 'ent-adventure-zone-by-adventure-hq-dubai',
        'title': 'Buy One Get One Free at Adventure Zone by Adventure HQ via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/adventure-zone-by-adventure-hq-dubai/detail',
    },
    {
        'place_slug': 'dominos-pizza-dubai',
        'discount_slug': 'ent-dominos-pizza-dubai',
        'title': "Buy One Get One Free at Domino's Pizza via The Entertainer",
        'external_url': 'https://www.theentertainerme.com/outlets/dominos-pizza-dubai/detail',
    },
    {
        'place_slug': 'texas-chicken-dubai',
        'discount_slug': 'ent-texas-chicken-dubai',
        'title': 'Buy One Get One Free at Texas Chicken via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/texas-chicken-dubai/detail',
    },
    {
        'place_slug': 'nandos-dubai',
        'discount_slug': 'ent-nandos-dubai',
        'title': "Buy One Get One Free at Nando's via The Entertainer",
        'external_url': 'https://www.theentertainerme.com/outlets/nandos-dubai/detail',
    },
    {
        'place_slug': 'zafran-dubai',
        'discount_slug': 'ent-zafran-dubai',
        'title': 'Buy One Get One Free at Zafran via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/zafran-dubai/detail',
    },
    {
        'place_slug': 'tamani-marina-hotel-and-hotel-apartment',
        'discount_slug': 'ent-tamani-marina-hotel-and-hotel-apartment',
        'title': 'Buy One Get One Free at Tamani Marina Hotel and Hotel Apartment via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/tamani-marina-hotel-and-hotel-apartment/detail',
    },
    {
        'place_slug': 'dubai-autodrome',
        'discount_slug': 'ent-dubai-autodrome',
        'title': 'Buy One Get One Free at Dubai Autodrome via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/dubai-autodrome/detail',
    },
    {
        'place_slug': 'carluccios-dubai',
        'discount_slug': 'ent-carluccios-dubai',
        'title': "Buy One Get One Free at Carluccio's via The Entertainer",
        'external_url': 'https://www.theentertainerme.com/outlets/carluccios-dubai/detail',
    },
    {
        'place_slug': 'burger-king-dubai',
        'discount_slug': 'ent-burger-king-dubai',
        'title': 'Buy One Get One Free at Burger King via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/burger-king-dubai/detail',
    },
    {
        'place_slug': 'tim-hortons-dubai',
        'discount_slug': 'ent-tim-hortons-dubai',
        'title': 'Buy One Get One Free at Tim Hortons via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/tim-hortons-dubai/detail',
    },
    {
        'place_slug': 'dunkin-dubai',
        'discount_slug': 'ent-dunkin-dubai',
        'title': "Buy One Get One Free at Dunkin' via The Entertainer",
        'external_url': 'https://www.theentertainerme.com/outlets/dunkin-dubai/detail',
    },
    {
        'place_slug': 'the-yellow-boats-dubai',
        'discount_slug': 'ent-the-yellow-boats-dubai',
        'title': 'Buy One Get One Free at The Yellow Boats via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/the-yellow-boats-dubai/detail',
    },
    {
        'place_slug': 'cold-stone-creamery-dubai',
        'discount_slug': 'ent-cold-stone-creamery-dubai',
        'title': 'Buy One Get One Free at Cold Stone Creamery Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/cold-stone-creamery-dubai/detail',
    },
    {
        'place_slug': 'hair-works-beauty-dubai',
        'discount_slug': 'ent-hair-works-beauty-dubai',
        'title': 'Buy One Get One Free at Hair Works Beauty via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/hair-works-beauty-dubai/detail',
    },
    {
        'place_slug': 'the-spa-hilton-jbr',
        'discount_slug': 'ent-the-spa-hilton-jbr',
        'title': 'Buy One Get One Free at The Spa - Hilton JBR via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/the-spa-hilton-jbr/detail',
    },
    {
        'place_slug': 'buffalo-wings-rings-dubai',
        'discount_slug': 'ent-buffalo-wings-rings-dubai',
        'title': 'Buy One Get One Free at Buffalo Wings & Rings via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/buffalo-wings-rings-dubai/detail',
    },
    {
        'place_slug': 'sofitel-spa-dubai-downtown',
        'discount_slug': 'ent-sofitel-spa-dubai-downtown',
        'title': 'Buy One Get One Free at Sofitel SPA Dubai Downtown via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/sofitel-spa-dubai-downtown/detail',
    },
    {
        'place_slug': 'vivaldi-restaurant-dubai',
        'discount_slug': 'ent-vivaldi-restaurant-dubai',
        'title': 'Buy One Get One Free at Vivaldi Restaurant via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/vivaldi-restaurant-dubai/detail',
    },
    {
        'place_slug': 'la-brioche-dubai',
        'discount_slug': 'ent-la-brioche-dubai',
        'title': 'Buy One Get One Free at La Brioche via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/la-brioche-dubai/detail',
    },
    {
        'place_slug': 'shang-palace-at-shangri-la-dubai',
        'discount_slug': 'ent-shang-palace-at-shangri-la-dubai',
        'title': 'Buy One Get One Free at Shang Palace at Shangri-La Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/shang-palace-at-shangri-la-dubai/detail',
    },
    {
        'place_slug': 'tony-romas-dubai',
        'discount_slug': 'ent-tony-romas-dubai',
        'title': "Buy One Get One Free at Tony Roma's via The Entertainer",
        'external_url': 'https://www.theentertainerme.com/outlets/tony-romas-dubai/detail',
    },
    {
        'place_slug': 'papa-johns-pizza-dubai',
        'discount_slug': 'ent-papa-johns-pizza-dubai',
        'title': 'Buy One Get One Free at Papa Johns Pizza via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/papa-johns-pizza-dubai/detail',
    },
    {
        'place_slug': 'escape-hunt-dubai',
        'discount_slug': 'ent-escape-hunt-dubai',
        'title': 'Buy One Get One Free at Escape Hunt via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/escape-hunt-dubai/detail',
    },
    {
        'place_slug': 'fun-block-dubai',
        'discount_slug': 'ent-fun-block-dubai',
        'title': 'Buy One Get One Free at Fun Block via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/fun-block-dubai/detail',
    },
    {
        'place_slug': 'belgian-beer-caf-madinat-jumeirah',
        'discount_slug': 'ent-belgian-beer-caf-madinat-jumeirah',
        'title': 'Buy One Get One Free at Belgian Beer Cafe Madinat Jumeirah via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/belgian-beer-caf-madinat-jumeirah/detail',
    },
    {
        'place_slug': 'ctaste-centro-al-barsha',
        'discount_slug': 'ent-ctaste-centro-al-barsha',
        'title': 'Buy One Get One Free at c.taste - Centro Barsha via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/ctaste-centro-al-barsha/detail',
    },
    {
        'place_slug': 'wyndham-dubai-marina',
        'discount_slug': 'ent-wyndham-dubai-marina',
        'title': 'Buy One Get One Free at The First Collection Marina via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/wyndham-dubai-marina/detail',
    },
    {
        'place_slug': 'dennys-dubai',
        'discount_slug': 'ent-dennys-dubai',
        'title': "Buy One Get One Free at Denny's via The Entertainer",
        'external_url': 'https://www.theentertainerme.com/outlets/dennys-dubai/detail',
    },
    {
        'place_slug': 'the-rose-crown-dubai',
        'discount_slug': 'ent-the-rose-crown-dubai',
        'title': 'Buy One Get One Free at The Rose & Crown Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/the-rose-crown-dubai/detail',
    },
    {
        'place_slug': 'chloes-beauty-hair-nails-dubai',
        'discount_slug': 'ent-chloes-beauty-hair-nails-dubai',
        'title': "Buy One Get One Free at Chloe's Beauty, Hair & Nails via The Entertainer",
        'external_url': 'https://www.theentertainerme.com/outlets/chloes-beauty-hair-nails-dubai/detail',
    },
    {
        'place_slug': 'metropolitan-hotel-dubai',
        'discount_slug': 'ent-metropolitan-hotel-dubai',
        'title': 'Buy One Get One Free at Metropolitan Hotel Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/metropolitan-hotel-dubai/detail',
    },
    {
        'place_slug': 'soul-senses-spa-wellness-dubai',
        'discount_slug': 'ent-soul-senses-spa-wellness-dubai',
        'title': 'Buy One Get One Free at Soul Senses Spa & Wellness Standard - Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/soul-senses-spa-wellness-dubai/detail',
    },
    {
        'place_slug': 'lucky-voice-dubai',
        'discount_slug': 'ent-lucky-voice-dubai',
        'title': 'Buy One Get One Free at Lucky Voice Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/lucky-voice-dubai/detail',
    },
    {
        'place_slug': 'doner-gyros-dubai',
        'discount_slug': 'ent-doner-gyros-dubai',
        'title': 'Buy One Get One Free at Doner & Gyros Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/doner-gyros-dubai/detail',
    },
    {
        'place_slug': 'champion-cleaners-dubai',
        'discount_slug': 'ent-champion-cleaners-dubai',
        'title': 'Buy One Get One Free at Champion Cleaners via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/champion-cleaners-dubai/detail',
    },
    {
        'place_slug': 'tryp-by-wyndham-dubai',
        'discount_slug': 'ent-tryp-by-wyndham-dubai',
        'title': 'Buy One Get One Free at TRYP by Wyndham Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/tryp-by-wyndham-dubai/detail',
    },
    {
        'place_slug': 'lock-stock-barrel-jbr',
        'discount_slug': 'ent-lock-stock-barrel-jbr',
        'title': 'Buy One Get One Free at Lock Stock & Barrel via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/lock-stock-barrel-jbr/detail',
    },
    {
        'place_slug': 'belgian-beer-cafe-dubai',
        'discount_slug': 'ent-belgian-beer-cafe-dubai',
        'title': 'Buy One Get One Free at Belgian Beer Cafe via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/belgian-beer-cafe-dubai/detail',
    },
    {
        'place_slug': 'park-inn-by-radisson-dubai-motor-city',
        'discount_slug': 'ent-park-inn-by-radisson-dubai-motor-city',
        'title': 'Buy One Get One Free at Park Inn by Radisson, Dubai Motor City via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/park-inn-by-radisson-dubai-motor-city/detail',
    },
    {
        'place_slug': 'grand-hyatt-dubai',
        'discount_slug': 'ent-grand-hyatt-dubai',
        'title': 'Buy One Get One Free at Grand Hyatt Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/grand-hyatt-dubai/detail',
    },
    {
        'place_slug': 'dunes-cafe-at-shangri-la-dubai',
        'discount_slug': 'ent-dunes-cafe-at-shangri-la-dubai',
        'title': 'Buy One Get One Free at Dunes Cafe at Shangri-La Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/dunes-cafe-at-shangri-la-dubai/detail',
    },
    {
        'place_slug': 'off-the-hook-dubai',
        'discount_slug': 'ent-off-the-hook-dubai',
        'title': 'Buy One Get One Free at Off The HOOK via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/off-the-hook-dubai/detail',
    },
    {
        'place_slug': 'radisson-blu-hotel-dubai-waterfront',
        'discount_slug': 'ent-radisson-blu-hotel-dubai-waterfront',
        'title': 'Buy One Get One Free at Radisson Blu Hotel, Dubai Waterfront via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/radisson-blu-hotel-dubai-waterfront/detail',
    },
    {
        'place_slug': 'the-larder-radisson-blu-hotel-dubai-waterfront',
        'discount_slug': 'ent-the-larder-radisson-blu-hotel-dubai-waterfront',
        'title': 'Buy One Get One Free at The Larder - Radisson Blu Hotel, Dubai Waterfront via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/the-larder-radisson-blu-hotel-dubai-waterfront/detail',
    },
    {
        'place_slug': 'trader-vics-hilton-dubai-jumeirah',
        'discount_slug': 'ent-trader-vics-hilton-dubai-jumeirah',
        'title': "Buy One Get One Free at Trader Vic's - JBR via The Entertainer",
        'external_url': 'https://www.theentertainerme.com/outlets/trader-vics-hilton-dubai-jumeirah/detail',
    },
    {
        'place_slug': 'esthetic-sense-dubai',
        'discount_slug': 'ent-esthetic-sense-dubai',
        'title': 'Buy One Get One Free at Esthetic Sense Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/esthetic-sense-dubai/detail',
    },
    {
        'place_slug': 'cafe-bateel-dubai',
        'discount_slug': 'ent-cafe-bateel-dubai',
        'title': 'Buy One Get One Free at Cafe Bateel - Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/cafe-bateel-dubai/detail',
    },
    {
        'place_slug': 'pizza-di-rocco-dubai',
        'discount_slug': 'ent-pizza-di-rocco-dubai',
        'title': 'Buy One Get One Free at Pizza Di Rocco via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/pizza-di-rocco-dubai/detail',
    },
    {
        'place_slug': 'the-lounge-dubai',
        'discount_slug': 'ent-the-lounge-dubai',
        'title': 'Buy One Get One Free at The Lounge via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/the-lounge-dubai/detail',
    },
    {
        'place_slug': 'famous-daves-dubai',
        'discount_slug': 'ent-famous-daves-dubai',
        'title': "Buy One Get One Free at Famous Dave's - Dubai via The Entertainer",
        'external_url': 'https://www.theentertainerme.com/outlets/famous-daves-dubai/detail',
    },
    {
        'place_slug': 'tepfactor-dubai',
        'discount_slug': 'ent-tepfactor-dubai',
        'title': 'Buy One Get One Free at TEPfactor via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/tepfactor-dubai/detail',
    },
    {
        'place_slug': 'the-pizza-pie-factory-dubai',
        'discount_slug': 'ent-the-pizza-pie-factory-dubai',
        'title': 'Buy One Get One Free at The Pizza Pie Factory via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/the-pizza-pie-factory-dubai/detail',
    },
    {
        'place_slug': 'focus-restaurant-hyatt-place-dubai-wasl-district',
        'discount_slug': 'ent-focus-restaurant-hyatt-place-dubai-wasl-district',
        'title': 'Buy One Get One Free at Focus Restaurant - Hyatt Place Dubai Wasl District via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/focus-restaurant-hyatt-place-dubai-wasl-district/detail',
    },
    {
        'place_slug': 'dubai-explorers',
        'discount_slug': 'ent-dubai-explorers',
        'title': 'Buy One Get One Free at Dubai Explorers via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/dubai-explorers/detail',
    },
    {
        'place_slug': 'trampo-extreme-dubai-mall',
        'discount_slug': 'ent-trampo-extreme-dubai-mall',
        'title': 'Buy One Get One Free at TRAMPO via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/trampo-extreme-dubai-mall/detail',
    },
    {
        'place_slug': 'focus-bar-jumeirah',
        'discount_slug': 'ent-focus-bar-jumeirah',
        'title': 'Buy One Get One Free at Focus Bar - Jumeirah via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/focus-bar-jumeirah/detail',
    },
    {
        'place_slug': 'poke-co-dubai',
        'discount_slug': 'ent-poke-co-dubai',
        'title': 'Buy One Get One Free at Poke & Co. via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/poke-co-dubai/detail',
    },
    {
        'place_slug': 'focus-restaurant-jumeirah',
        'discount_slug': 'ent-focus-restaurant-jumeirah',
        'title': 'Buy One Get One Free at Focus Restaurant - Jumeirah via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/focus-restaurant-jumeirah/detail',
    },
    {
        'place_slug': 'bab-al-qasr-hotel-pool',
        'discount_slug': 'ent-bab-al-qasr-hotel-pool',
        'title': 'Buy One Get One Free at Bab Al Qasr Hotel Pool & Beach via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/bab-al-qasr-hotel-pool/detail',
    },
    {
        'place_slug': 'the-larder-radisson-blu-hotel-dubai-canal-view',
        'discount_slug': 'ent-the-larder-radisson-blu-hotel-dubai-canal-view',
        'title': 'Buy One Get One Free at The Larder - Radisson Blu Hotel, Dubai Canal View via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/the-larder-radisson-blu-hotel-dubai-canal-view/detail',
    },
    {
        'place_slug': 'molten-chocolate-cafe-dubai',
        'discount_slug': 'ent-molten-chocolate-cafe-dubai',
        'title': 'Buy One Get One Free at Molten Chocolate Cafe via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/molten-chocolate-cafe-dubai/detail',
    },
    {
        'place_slug': 'beyond-pancakes-marina-square',
        'discount_slug': 'ent-beyond-pancakes-marina-square',
        'title': 'Buy One Get One Free at Beyond Pancakes Marina Square via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/beyond-pancakes-marina-square/detail',
    },
    {
        'place_slug': 'wox-hyatt-place-dubai-jumeirah',
        'discount_slug': 'ent-wox-hyatt-place-dubai-jumeirah',
        'title': 'Buy One Get One Free at Wox - Hyatt Place Dubai Jumeirah via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/wox-hyatt-place-dubai-jumeirah/detail',
    },
    {
        'place_slug': 'radisson-blu-hotel-dubai-canal-view',
        'discount_slug': 'ent-radisson-blu-hotel-dubai-canal-view',
        'title': 'Buy One Get One Free at Radisson Blu Hotel, Dubai Canal View via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/radisson-blu-hotel-dubai-canal-view/detail',
    },
    {
        'place_slug': 'harrys-marina-bay',
        'discount_slug': 'ent-harrys-marina-bay',
        'title': "Buy One Get One Free at Harry's Marina Bay via The Entertainer",
        'external_url': 'https://www.theentertainerme.com/outlets/harrys-marina-bay/detail',
    },
    {
        'place_slug': 'ginos-deli-dubai',
        'discount_slug': 'ent-ginos-deli-dubai',
        'title': "Buy One Get One Free at Gino's Deli via The Entertainer",
        'external_url': 'https://www.theentertainerme.com/outlets/ginos-deli-dubai/detail',
    },
    {
        'place_slug': 'taj-dubai',
        'discount_slug': 'ent-taj-dubai',
        'title': 'Buy One Get One Free at Taj Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/taj-dubai/detail',
    },
    {
        'place_slug': 'andaz-dubai-the-palm',
        'discount_slug': 'ent-andaz-dubai-the-palm',
        'title': 'Buy One Get One Free at Hyatt Andaz Dubai The Palm via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/andaz-dubai-the-palm/detail',
    },
    {
        'place_slug': 'kimura-ya-authentic-japanese-restaurant-anantara-downtown-dubai-hotel',
        'discount_slug': 'ent-kimura-ya-authentic-japanese-restaurant-anantara-downtown-dubai-hotel',
        'title': 'Buy One Get One Free at Kimura-ya Authentic Japanese Restaurant via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/kimura-ya-authentic-japanese-restaurant-anantara-downtown-dubai-hotel/detail',
    },
    {
        'place_slug': 'dubai-dream-casters',
        'discount_slug': 'ent-dubai-dream-casters',
        'title': 'Buy One Get One Free at Dubai Dream Casters via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/dubai-dream-casters/detail',
    },
    {
        'place_slug': 'staybridge-suites-dubai-al-maktoum-airport',
        'discount_slug': 'ent-staybridge-suites-dubai-al-maktoum-airport',
        'title': 'Buy One Get One Free at Staybridge Suites Dubai Al-Maktoum Airport via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/staybridge-suites-dubai-al-maktoum-airport/detail',
    },
    {
        'place_slug': 'holiday-inn-dubai-al-maktoum-airport',
        'discount_slug': 'ent-holiday-inn-dubai-al-maktoum-airport',
        'title': 'Buy One Get One Free at Holiday Inn Dubai Al-Maktoum Airport via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/holiday-inn-dubai-al-maktoum-airport/detail',
    },
    {
        'place_slug': 'the-pool-at-doubletree-by-hilton-hotel-dubai-jumeirah-beach',
        'discount_slug': 'ent-the-pool-at-doubletree-by-hilton-hotel-dubai-jumeirah-beach',
        'title': 'Buy One Get One Free at DoubleTree by Hilton JBR - Pool & Beach via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/the-pool-at-doubletree-by-hilton-hotel-dubai-jumeirah-beach/detail',
    },
    {
        'place_slug': 'explorers-dubai',
        'discount_slug': 'ent-explorers-dubai',
        'title': 'Buy One Get One Free at Explorers Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/explorers-dubai/detail',
    },
    {
        'place_slug': 'hurricanes-grill-dubai-mall',
        'discount_slug': 'ent-hurricanes-grill-dubai-mall',
        'title': "Buy One Get One Free at Hurricane's Grill via The Entertainer",
        'external_url': 'https://www.theentertainerme.com/outlets/hurricanes-grill-dubai-mall/detail',
    },
    {
        'place_slug': 'dubai-adventures',
        'discount_slug': 'ent-dubai-adventures',
        'title': 'Buy One Get One Free at Dubai Adventures via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/dubai-adventures/detail',
    },
    {
        'place_slug': 'carnival-by-tresind-dubai',
        'discount_slug': 'ent-carnival-by-tresind-dubai',
        'title': 'Buy One Get One Free at Carnival by Tresind via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/carnival-by-tresind-dubai/detail',
    },
    {
        'place_slug': 'dubai-trip',
        'discount_slug': 'ent-dubai-trip',
        'title': 'Buy One Get One Free at Dubai Trip via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/dubai-trip/detail',
    },
    {
        'place_slug': '800-pizza-authentic-italian-pizza-dubai',
        'discount_slug': 'ent-800-pizza-authentic-italian-pizza-dubai',
        'title': 'Buy One Get One Free at 800 PIZZA Authentic Italian Pizza via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/800-pizza-authentic-italian-pizza-dubai/detail',
    },
    {
        'place_slug': 'dubai-buggy-riders',
        'discount_slug': 'ent-dubai-buggy-riders',
        'title': 'Buy One Get One Free at Dubai Buggy Riders via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/dubai-buggy-riders/detail',
    },
    {
        'place_slug': 'sizzling-wok-dubai',
        'discount_slug': 'ent-sizzling-wok-dubai',
        'title': 'Buy One Get One Free at Sizzling Wok, Business Bay via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/sizzling-wok-dubai/detail',
    },
    {
        'place_slug': 'chicking-dubai',
        'discount_slug': 'ent-chicking-dubai',
        'title': 'Buy One Get One Free at ChicKing - Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/chicking-dubai/detail',
    },
    {
        'place_slug': 'the-app-tutorial-dubai',
        'discount_slug': 'ent-the-app-tutorial-dubai',
        'title': 'Buy One Get One Free at When, Where & How to Use our App via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/the-app-tutorial-dubai/detail',
    },
    {
        'place_slug': 'dubai-activities',
        'discount_slug': 'ent-dubai-activities',
        'title': 'Buy One Get One Free at Dubai Activities via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/dubai-activities/detail',
    },
    {
        'place_slug': 'sushi-library-dubai',
        'discount_slug': 'ent-sushi-library-dubai',
        'title': 'Buy One Get One Free at Sushi Library via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/sushi-library-dubai/detail',
    },
    {
        'place_slug': 'legoland-dubai',
        'discount_slug': 'ent-legoland-dubai',
        'title': 'Buy One Get One Free at LEGOLAND® Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/legoland-dubai/detail',
    },
    {
        'place_slug': 'motiongate-dubai',
        'discount_slug': 'ent-motiongate-dubai',
        'title': 'Buy One Get One Free at MOTIONGATE™ Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/motiongate-dubai/detail',
    },
    {
        'place_slug': 'the-first-collection-at-jumeirah-village-circle',
        'discount_slug': 'ent-the-first-collection-at-jumeirah-village-circle',
        'title': 'Buy One Get One Free at The First Collection at Jumeirah Village Circle via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/the-first-collection-at-jumeirah-village-circle/detail',
    },
    {
        'place_slug': 'soul-senses-spa-wellness-premium-dubai',
        'discount_slug': 'ent-soul-senses-spa-wellness-premium-dubai',
        'title': 'Buy One Get One Free at Soul Senses Spa & Wellness Premium - Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/soul-senses-spa-wellness-premium-dubai/detail',
    },
    {
        'place_slug': 'isola-restaurant-dubai',
        'discount_slug': 'ent-isola-restaurant-dubai',
        'title': 'Buy One Get One Free at Isola Restaurant Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/isola-restaurant-dubai/detail',
    },
    {
        'place_slug': 'mygolf-dubai',
        'discount_slug': 'ent-mygolf-dubai',
        'title': 'Buy One Get One Free at MyGolf Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/mygolf-dubai/detail',
    },
    {
        'place_slug': 'burger-queen-dubai',
        'discount_slug': 'ent-burger-queen-dubai',
        'title': 'Buy One Get One Free at Burger 52 via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/burger-queen-dubai/detail',
    },
    {
        'place_slug': 'punjab-grill-dubai',
        'discount_slug': 'ent-punjab-grill-dubai',
        'title': 'Buy One Get One Free at Punjab Grill via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/punjab-grill-dubai/detail',
    },
    {
        'place_slug': 'aloft-palm-jumeirah-pool-beach',
        'discount_slug': 'ent-aloft-palm-jumeirah-pool-beach',
        'title': 'Buy One Get One Free at Aloft Palm Jumeirah - Pool & Beach via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/aloft-palm-jumeirah-pool-beach/detail',
    },
    {
        'place_slug': 'the-first-collection-business-bay',
        'discount_slug': 'ent-the-first-collection-business-bay',
        'title': 'Buy One Get One Free at The First Collection Business Bay via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/the-first-collection-business-bay/detail',
    },
    {
        'place_slug': 'taj-dubai-gym-and-pool',
        'discount_slug': 'ent-taj-dubai-gym-and-pool',
        'title': 'Buy One Get One Free at Taj Dubai Gym and Pool via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/taj-dubai-gym-and-pool/detail',
    },
    {
        'place_slug': 'lantica-pizzeria-by-michele-dubai-hills-mall',
        'discount_slug': 'ent-lantica-pizzeria-by-michele-dubai-hills-mall',
        'title': "Buy One Get One Free at L'Antica Pizzeria by Michele via The Entertainer",
        'external_url': 'https://www.theentertainerme.com/outlets/lantica-pizzeria-by-michele-dubai-hills-mall/detail',
    },
    {
        'place_slug': 'honest-bowl-dubai',
        'discount_slug': 'ent-honest-bowl-dubai',
        'title': 'Buy One Get One Free at Honest Bowl via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/honest-bowl-dubai/detail',
    },
    {
        'place_slug': 'momo-bros-dubai',
        'discount_slug': 'ent-momo-bros-dubai',
        'title': 'Buy One Get One Free at Momo Bros via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/momo-bros-dubai/detail',
    },
    {
        'place_slug': 'radisson-red-dubai-silicon-oasis',
        'discount_slug': 'ent-radisson-red-dubai-silicon-oasis',
        'title': 'Buy One Get One Free at Radisson RED Dubai Silicon Oasis via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/radisson-red-dubai-silicon-oasis/detail',
    },
    {
        'place_slug': 'madame-tussauds-dubai',
        'discount_slug': 'ent-madame-tussauds-dubai',
        'title': 'Buy One Get One Free at Madame Tussauds Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/madame-tussauds-dubai/detail',
    },
    {
        'place_slug': 'cosmic-kitchen-al-barsha',
        'discount_slug': 'ent-cosmic-kitchen-al-barsha',
        'title': 'Buy One Get One Free at Cosmic Kitchen, Al Barsha via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/cosmic-kitchen-al-barsha/detail',
    },
    {
        'place_slug': 'maiora-at-nh-collection-dubai-the-palm',
        'discount_slug': 'ent-maiora-at-nh-collection-dubai-the-palm',
        'title': 'Buy One Get One Free at Maiora via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/maiora-at-nh-collection-dubai-the-palm/detail',
    },
    {
        'place_slug': 'mandarin-oak-dubai',
        'discount_slug': 'ent-mandarin-oak-dubai',
        'title': 'Buy One Get One Free at Mandarin Oak via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/mandarin-oak-dubai/detail',
    },
    {
        'place_slug': 'behrouz-biryani-dubai',
        'discount_slug': 'ent-behrouz-biryani-dubai',
        'title': 'Buy One Get One Free at Behrouz Biryani via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/behrouz-biryani-dubai/detail',
    },
    {
        'place_slug': 'fricken-chicken-dubai',
        'discount_slug': 'ent-fricken-chicken-dubai',
        'title': 'Buy One Get One Free at Fricken Chicken via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/fricken-chicken-dubai/detail',
    },
    {
        'place_slug': 'the-500-calorie-project-dubai',
        'discount_slug': 'ent-the-500-calorie-project-dubai',
        'title': 'Buy One Get One Free at The 500 Calorie Project via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/the-500-calorie-project-dubai/detail',
    },
    {
        'place_slug': 'blackout-horror-escape-room-dubai',
        'discount_slug': 'ent-blackout-horror-escape-room-dubai',
        'title': 'Buy One Get One Free at Blackout Horror Escape Room via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/blackout-horror-escape-room-dubai/detail',
    },
    {
        'place_slug': 'desert-rose-tourism-dubai',
        'discount_slug': 'ent-desert-rose-tourism-dubai',
        'title': 'Buy One Get One Free at Desert Rose Tourism via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/desert-rose-tourism-dubai/detail',
    },
    {
        'place_slug': 'bateel-elan-difc',
        'discount_slug': 'ent-bateel-elan-difc',
        'title': "Buy One Get One Free at Bateel El'an - Dubai via The Entertainer",
        'external_url': 'https://www.theentertainerme.com/outlets/bateel-elan-difc/detail',
    },
    {
        'place_slug': 'the-spa-at-intercontinental-dubai-festival-city',
        'discount_slug': 'ent-the-spa-at-intercontinental-dubai-festival-city',
        'title': 'Buy One Get One Free at The Spa at InterContinental Dubai Festival City via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/the-spa-at-intercontinental-dubai-festival-city/detail',
    },
    {
        'place_slug': 'holiday-inn-dubai-business-bay',
        'discount_slug': 'ent-holiday-inn-dubai-business-bay',
        'title': 'Buy One Get One Free at Holiday Inn Dubai Business Bay via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/holiday-inn-dubai-business-bay/detail',
    },
    {
        'place_slug': 'dubai-yachts',
        'discount_slug': 'ent-dubai-yachts',
        'title': 'Buy One Get One Free at Dubai Yachts via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/dubai-yachts/detail',
    },
    {
        'place_slug': 'jbr-perk',
        'discount_slug': 'ent-jbr-perk',
        'title': 'Buy One Get One Free at JBR Perk via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/jbr-perk/detail',
    },
    {
        'place_slug': 'dubai-tourism-and-travel',
        'discount_slug': 'ent-dubai-tourism-and-travel',
        'title': 'Buy One Get One Free at Dubai Tourism and Travel via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/dubai-tourism-and-travel/detail',
    },
    {
        'place_slug': 'halo-halo-marina',
        'discount_slug': 'ent-halo-halo-marina',
        'title': 'Buy One Get One Free at Halo Halo - Marina via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/halo-halo-marina/detail',
    },
    {
        'place_slug': 'holiday-inn-suites-dubai-science-park',
        'discount_slug': 'ent-holiday-inn-suites-dubai-science-park',
        'title': 'Buy One Get One Free at Holiday Inn & Suites Dubai Science Park via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/holiday-inn-suites-dubai-science-park/detail',
    },
    {
        'place_slug': 'palazzo-versace-dubai',
        'discount_slug': 'ent-palazzo-versace-dubai',
        'title': 'Buy One Get One Free at Palazzo Versace Dubai via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/palazzo-versace-dubai/detail',
    },
    {
        'place_slug': 'pinsa-romana-dubai',
        'discount_slug': 'ent-pinsa-romana-dubai',
        'title': 'Buy One Get One Free at Pinsa Romana via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/pinsa-romana-dubai/detail',
    },
    {
        'place_slug': 'anantara-downtown-dubai-hotel',
        'discount_slug': 'ent-anantara-downtown-dubai-hotel',
        'title': 'Buy One Get One Free at Anantara Downtown Dubai Hotel via The Entertainer',
        'external_url': 'https://www.theentertainerme.com/outlets/anantara-downtown-dubai-hotel/detail',
    },
]


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
EXPERIENCE_KEYWORDS = {
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
}


def add_entertainer(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Discount = apps.get_model("discounts", "Discount")
    Experience = apps.get_model("places", "Experience")

    place_by_slug = {}
    for spec in PLACES:
        place, _ = Place.objects.get_or_create(
            slug=spec["slug"],
            defaults={
                "name": spec["name"],
                "category": "restaurant",  # Entertainer is mostly food/drink
                "area": spec["area"],
                "address": "",
                "phone": "",
                "website": "",  # filled by hotel-keyword backfill below
                "description": (
                    f'{spec["name"]} — Dubai outlet listed on The '
                    f'Entertainer. Buy-one-get-one-free offers; details '
                    f'on theentertainerme.com.'
                ),
                "is_published": True,
            },
        )
        place_by_slug[spec["slug"]] = place

    for d in DISCOUNTS:
        place = place_by_slug.get(d["place_slug"])
        if place is None:
            continue
        Discount.objects.update_or_create(
            slug=d["discount_slug"],
            defaults={
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
            },
        )

    # Backfill website on all websiteless places (only the new ones,
    # since older places already got 0014's pass).
    for p in Place.objects.filter(website=""):
        haystack = " ".join([p.name or "", p.area or "", p.address or ""]).lower()
        for keyword, domain in HOTEL_KEYWORDS:
            if keyword in haystack:
                Place.objects.filter(pk=p.pk).update(website=f"https://www.{domain}/")
                break

    # Auto-tag experiences on places without any experience yet.
    by_slug = {e.slug: e for e in Experience.objects.all()}
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
