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
