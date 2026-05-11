from django.db.models import Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.discounts.models import Discount, DiscountProgram
from apps.places.models import Category, Experience, Place


@require_GET
def home(request):
    # Discounts the current user is allowed to see.
    visible_discounts = Discount.objects.live().select_related("place")
    if not request.user.is_authenticated:
        visible_discounts = visible_discounts.filter(
            is_members_only=False,
            place__is_members_only=False,
        )

    # Filter inputs.
    q = request.GET.get("q", "").strip()
    selected_programs = [s for s in request.GET.getlist("programs") if s]
    selected_experiences = [s for s in request.GET.getlist("experiences") if s]
    only_gems = request.GET.get("gems") == "1"

    # Base set: published places that have at least one visible discount.
    place_ids = list(visible_discounts.values_list("place_id", flat=True).distinct())
    places_qs = Place.objects.filter(id__in=place_ids, is_published=True)
    if not request.user.is_authenticated:
        places_qs = places_qs.filter(is_members_only=False)

    # Apply search.
    if q:
        places_qs = places_qs.filter(
            Q(name__icontains=q)
            | Q(area__icontains=q)
            | Q(address__icontains=q)
            | Q(description__icontains=q)
        )

    # Apply program filter — place matches if any visible discount uses one of the selected programs.
    if selected_programs:
        places_qs = places_qs.filter(
            discounts__source_program__in=selected_programs,
            discounts__is_active=True,
        ).distinct()

    # Apply experience filter — place must have at least one of the selected tags.
    if selected_experiences:
        places_qs = places_qs.filter(experiences__slug__in=selected_experiences).distinct()

    # Apply gems filter — at least one featured discount.
    if only_gems:
        places_qs = places_qs.filter(
            discounts__is_featured=True,
            discounts__is_active=True,
        ).distinct()

    places_qs = places_qs.prefetch_related(
        Prefetch("discounts", queryset=visible_discounts, to_attr="visible_discounts")
    ).order_by("name")

    places = list(places_qs)
    for place in places:
        seen: set[str] = set()
        place.programs = []
        for d in place.visible_discounts:
            if d.source_program and d.source_program not in seen:
                seen.add(d.source_program)
                place.programs.append({
                    "value": d.source_program,
                    "label": d.get_source_program_display(),
                })
        place.offer_count = len(place.visible_discounts)

    # Group places by category, preserving Category.choices order so the home
    # page reads top-to-bottom: restaurants → attractions → hotels → retail → services.
    by_cat: dict[str, list[Place]] = {value: [] for value, _ in Category.choices}
    for p in places:
        by_cat.setdefault(p.category, []).append(p)
    places_by_category = [
        (label, by_cat[value]) for value, label in Category.choices if by_cat.get(value)
    ]

    context = {
        "places": places,
        "places_by_category": places_by_category,
        "selected": {
            "q": q,
            "programs": selected_programs,
            "experiences": selected_experiences,
            "gems": only_gems,
        },
        "all_programs": DiscountProgram.choices,
        "all_experiences": list(Experience.objects.filter(is_active=True).order_by("sort_order", "label")),
        "active_filter_count": len(selected_programs) + len(selected_experiences) + (1 if only_gems else 0),
    }

    if request.headers.get("HX-Request"):
        return render(request, "pages/_home_results.html", context)
    return render(request, "pages/home.html", context)


@require_GET
def about(request):
    return render(request, "pages/about.html")


@require_GET
def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Allow: /",
        f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def handler404(request, exception=None):
    return render(request, "pages/404.html", status=404)


def handler500(request):
    return render(request, "pages/500.html", status=500)
