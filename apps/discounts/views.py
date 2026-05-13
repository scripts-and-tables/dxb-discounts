import json
import time
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from apps.places.models import Place

from .models import Program


def _venue_qs(program_slug: str, user) -> "QuerySet[Place]":
    place_filter = Q(is_published=True)
    if not user.is_authenticated:
        place_filter &= Q(is_members_only=False)
    return (
        Place.objects.filter(place_filter)
        .filter(discounts__source_program=program_slug, discounts__is_active=True)
        .distinct()
    )


@require_GET
def program_list(request):
    """Directory of UAE discount programs (Fazaa, Esaad, Entertainer, …)."""
    programs = list(Program.objects.filter(is_published=True))
    for p in programs:
        p.venue_count = _venue_qs(p.slug, request.user).count()
    return render(request, "discounts/list.html", {"programs": programs})


@require_GET
def program_detail(request, slug: str):
    """Program info + venues that accept this program."""
    program = get_object_or_404(Program, slug=slug, is_published=True)
    venues = _venue_qs(program.slug, request.user).order_by("name")
    return render(request, "discounts/program_detail.html", {
        "program": program,
        "venues": venues,
    })


# Referrals page — module-level cache so we don't re-parse the JSON every
# request. The file is tiny today (~5 programs) but the dict here is what
# the template loops over; cap TTL at 6h so refresh-referrals runs land
# without a server restart.
_REFERRALS_CACHE: dict = {"at": 0.0, "value": []}
_REFERRALS_TTL_SECS = 6 * 3600


def _logo_domain(url: str) -> str:
    if not url:
        return ""
    netloc = urlparse(url).netloc or urlparse(url).path
    return netloc.removeprefix("www.").strip("/")


def _load_referrals() -> list[dict]:
    now = time.monotonic()
    if _REFERRALS_CACHE["value"] and now - _REFERRALS_CACHE["at"] < _REFERRALS_TTL_SECS:
        return _REFERRALS_CACHE["value"]

    data_dir = Path(settings.BASE_DIR) / "data"
    # Prefer the verified output from refresh-referrals; fall back to the
    # hand-curated seed if it hasn't been run yet.
    for filename in ("referrals_enriched.json", "referral_seed.json"):
        path = data_dir / filename
        if path.exists():
            with path.open(encoding="utf-8") as f:
                rows = json.load(f)
            break
    else:
        rows = []

    for r in rows:
        domain = _logo_domain(r.get("website") or r.get("referral_url", ""))
        r["logo_url"] = f"https://logo.clearbit.com/{domain}" if domain else ""
        r["favicon_url"] = f"https://www.google.com/s2/favicons?domain={domain}&sz=128" if domain else ""
        # Status badge:
        #   verified — fetcher saw a 200 and didn't flag it for review
        #   needs check — fetch failed or contents looked off
        if r.get("needs_review"):
            r["status_label"] = "Needs check"
            r["status_class"] = "chip"
        elif r.get("fetch_status") == 200:
            r["status_label"] = "Verified"
            r["status_class"] = "chip-amber"
        else:
            r["status_label"] = ""
            r["status_class"] = ""

    _REFERRALS_CACHE["at"] = now
    _REFERRALS_CACHE["value"] = rows
    return rows


@require_GET
def referrals(request):
    """Curated directory of UAE refer-and-earn programs."""
    return render(request, "discounts/referrals.html", {
        "referrals": _load_referrals(),
    })
