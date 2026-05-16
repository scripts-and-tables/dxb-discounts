# Loyalty program coverage

UAE-relevant loyalty / discount programs grouped by category, with the current state of integration in this project.

Columns:
- **In model** — has a `DiscountProgram` choice in `apps/discounts/models.py`
- **Has skill** — has a `refresh-*` Claude skill that pulls fresh data
- **Public catalog** — the source program exposes offer data without an auth wall
- **Fits our model** — the offer shape (per-venue flat discount, structured % or fixed-price) maps cleanly to `Discount` rows. Hotel-chain rate-discount and points-earning programs typically don't fit without schema changes.

Last updated: 2026-05-16.

---

## Membership / discount-card subscriptions

| Program | In model | Has skill | Public catalog | Fits our model | Notes |
|---|:-:|:-:|:-:|:-:|---|
| **Entertainer** | ✓ | ✓ | ✓ | ✓ | `refresh-entertainer`; ~9.6k UAE outlets |
| **Fazaa** | ✓ | ✓ | ✓ | ✓ | `refresh-fazaa`; ~7.7k UAE offers (federal employees) |
| **Esaad** | ✓ | ✗ | ✗ | ✓ | Auth-gated (Emirates ID / UAE PASS) — dead-end for scraping |
| Cobone | ✗ | ✗ | ✓ | ✓ | Daily-deals; smaller since 2020 |

## Hotel loyalty (UAE-specific or global with heavy UAE presence)

| Program | In model | Has skill | Public catalog | Fits our model | Notes |
|---|:-:|:-:|:-:|:-:|---|
| **Atlantis Circle** | ✓ | ✓ | ✓ | ✓ | `refresh-atlantis-circle`; 20 dining venues at The Palm + The Royal. Blue 15 / Silver 20 / Gold 25 / Black 30 %. |
| **U by Emaar** | ✓ | ✗ | ✓ | ✓ | Address / Vida / Armani; 1 U-point per AED. **Next candidate.** |
| Jumeirah One | ✗ | ✗ | ✓ | ✓ | Burj Al Arab, Madinat Jumeirah |
| GHA Discovery | ✗ | ✗ | ✓ | ~ | Anantara, Kempinski; tier-perks-driven, partial fit |
| Hilton Honors | ✗ | ✗ | ✓ | ✗ | Global; rate-discount + points, poor fit |
| Marriott Bonvoy | ✗ | ✗ | ✓ | ✗ | Global; same as Hilton |
| IHG One Rewards | ✗ | ✗ | ✓ | ~ | 25–30% dining at ME IHG hotels through Dec 2026 — that part fits |
| Accor ALL | ✗ | ✗ | ✓ | ✗ | Sofitel/Pullman/Novotel/Mövenpick/Rixos; rate-points |
| World of Hyatt | ✗ | ✗ | ✓ | ✗ | Park Hyatt, Grand Hyatt |
| FIVE Hotels | ✗ | ✗ | ✓ | ~ | FIVE Palm + FIVE Jumeirah Village |
| Rotana Rewards | ✗ | ✗ | ✓ | ✗ | Many UAE properties |
| The First Group Rewards | ✗ | ✗ | ✓ | ~ | Aparthotels |
| Anantara Nam Jai | ✗ | ✗ | ✓ | ~ | Anantara World Islands Dubai |
| Millennium My Stay | ✗ | ✗ | ✓ | ✗ | |

## Retail loyalty

| Program | In model | Has skill | Public catalog | Fits our model | Notes |
|---|:-:|:-:|:-:|:-:|---|
| **Shukran** | ✓ | ✗ | ~ | ~ | Landmark Group — points across Centrepoint, Splash, Babyshop |
| **SHARE Rewards** | ✓ | ✗ | ✓ | ~ | Majid Al Futtaim — Carrefour, VOX, Ski Dubai, Magic Planet |
| **Blue by Al-Futtaim** | ✓ | ✗ | ✓ | ~ | IKEA, ACE, Plug-Ins, Toys R Us |
| Al Tayer Amber | ✗ | ✗ | ✓ | ~ | Bloomingdale's, Harvey Nichols, Areej, Mamas & Papas |
| Club Apparel | ✗ | ✗ | ✓ | ~ | Apparel Group — 75+ brands (Levi's, ALDO, Tommy Hilfiger) |
| GMG Loyalty | ✗ | ✗ | ~ | ~ | Sun & Sand Sports, Nike, Columbia |
| Lulu Happiness | ✗ | ✗ | ✓ | ~ | Lulu Hypermarket |
| Spinneys PLUS | ✗ | ✗ | ✓ | ~ | Spinneys grocery |
| Choithrams | ✗ | ✗ | ✗ | ~ | Grocery |

## Banks (credit-card-driven offer programs)

| Program | In model | Has skill | Public catalog | Fits our model | Notes |
|---|:-:|:-:|:-:|:-:|---|
| ADCB TouchPoints | ✗ | ✗ | ✓ | ✓ | Public `offers.adcb.com` — VOX BOGO, Talabat 20%, Noon 15% |
| FAB Rewards | ✗ | ✗ | ✓ | ✓ | Manchester City card, Careem 20% |
| Emirates NBD Smiles | ✗ | ✗ | ✓ | ✓ | Massive lifestyle perks catalog |
| CBD Smiles | ✗ | ✗ | ~ | ✓ | Co-brand with Smiles |
| Mashreq Salaam | ✗ | ✗ | ~ | ~ | |
| HSBC Advance Rewards | ✗ | ✗ | ~ | ~ | |
| RAKBANK | ✗ | ✗ | ~ | ~ | |
| Standard Chartered 360 | ✗ | ✗ | ~ | ~ | |
| DIB Wala | ✗ | ✗ | ~ | ~ | |
| Liv. by ENBD | ✗ | ✗ | ~ | ~ | |

## Airlines

| Program | In model | Has skill | Public catalog | Fits our model | Notes |
|---|:-:|:-:|:-:|:-:|---|
| **Emirates Skywards** | ✓ | ✗ | ~ | ✗ | Miles-earning, not a discount catalog |
| Etihad Guest | ✗ | ✗ | ✓ | ~ | Etihad Guest Dining is a separate offer program |
| Air Arabia AirRewards | ✗ | ✗ | ✗ | ✗ | |
| Flydubai OPEN | ✗ | ✗ | ✗ | ✗ | |

## Telco

| Program | In model | Has skill | Public catalog | Fits our model | Notes |
|---|:-:|:-:|:-:|:-:|---|
| Etisalat Smiles (e&) | ✗ | ✗ | ~ | ~ | Lifestyle perks for postpaid subscribers |
| du Pay+ / Buzz | ✗ | ✗ | ~ | ~ | |

## Government / employee-only

| Program | In model | Has skill | Public catalog | Fits our model | Notes |
|---|:-:|:-:|:-:|:-:|---|
| **Fazaa** | ✓ | ✓ | ✓ | ✓ | |
| **Esaad** | ✓ | ✗ | ✗ | ✓ | Dead-end (auth) |
| Hayyak (Sharjah) | ✗ | ✗ | ~ | ✓ | |
| Watani Al Emarat | ✗ | ✗ | ~ | ✓ | |

## Private clubs (paid membership, in-house catalog)

| Program | In model | Has skill | Public catalog | Fits our model | Notes |
|---|:-:|:-:|:-:|:-:|---|
| **Elite Club** | ✓ | ✗ | ✓ | ✓ | Seeded manually |
| **Supper Club ME** | ✓ | ✗ | ✓ | ✓ | Seeded manually |
| **Emirates Platinum** | ✓ | ✗ | ✓ | ✓ | Seeded manually |
| **Zomato Pro / Gold** | ✓ | ✗ | ✗ | ✓ | Effectively defunct in UAE |
| **Repeat** | ✓ | ✗ | ✗ | ✗ | Defunct — team's now-product is Playbook (not an offers source) |

## Other (declined / not pursued)

| Program | Why declined |
|---|---|
| **Playbook** (my-playbook.com) | "Highlights" are venue programming (Ladies Night, Brunch) — freeform English, not structured discounts. Kept as a venue-metadata + icon-backfill source only. |

---

## Suggested next builds (in priority order)

These match our model cleanly (flat-% or per-venue structured discounts) and have public catalogs:

1. **`refresh-u-by-emaar`** — Address Hotels + Vida + Armani; same shape as Atlantis Circle (flat-% per tier across a finite venue list). Program row already seeded.
2. **`refresh-adcb-touchpoints`** — public `offers.adcb.com`; per-merchant discounts. Needs a new `DiscountProgram.ADCB_TOUCHPOINTS` choice + Program seed.
3. **`refresh-enbd-smiles`** — Emirates NBD Smiles app; very broad. Same notes as ADCB.
4. **`refresh-al-tayer-amber`** — luxury retail; Bloomingdale's, Harvey Nichols.

Hotel-chain programs (Marriott / Hilton / Accor / IHG) are held back — they're rate-discount + points-based, which doesn't fit the per-venue-flat-% shape without schema changes.
