import time

from django.db.models import Count, Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.discounts.models import Discount, DiscountProgram, DiscountType
from apps.places.models import Experience, Place


# In-process cache for the top-areas chip row. Areas churn on the order of
# weeks (only when ingest_offers introduces a brand in a new mall), so a
# coarse TTL is fine and keeps the home view from re-running this aggregate
# on every request.
_TOP_AREAS_CACHE: dict = {"at": 0.0, "value": []}
_TOP_AREAS_TTL_SECS = 3600
_MIN_PCT_OPTIONS = (20, 30, 50, 70)


def _top_areas(limit: int = 12) -> list[str]:
    now = time.monotonic()
    if _TOP_AREAS_CACHE["value"] and now - _TOP_AREAS_CACHE["at"] < _TOP_AREAS_TTL_SECS:
        return _TOP_AREAS_CACHE["value"]
    rows = (
        Place.objects.filter(is_published=True)
        .exclude(area="")
        .values("area")
        .annotate(n=Count("id"))
        .order_by("-n", "area")[:limit]
    )
    areas = [r["area"] for r in rows]
    _TOP_AREAS_CACHE["at"] = now
    _TOP_AREAS_CACHE["value"] = areas
    return areas


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
    selected_types = [s for s in request.GET.getlist("types") if s]
    selected_area = request.GET.get("area", "").strip()
    only_gems = request.GET.get("gems") == "1"
    try:
        min_pct = int(request.GET.get("min_pct", "") or 0)
    except ValueError:
        min_pct = 0
    # Snap to known buckets — guards against junk in the URL and keeps the
    # rendered chip row honest about which option is "selected".
    if min_pct not in _MIN_PCT_OPTIONS:
        min_pct = 0

    # Narrow visible_discounts by the offer-intrinsic filters first; the
    # downstream place_ids set is then naturally constrained to places that
    # have at least one matching offer.
    if selected_types:
        visible_discounts = visible_discounts.filter(discount_type__in=selected_types)
    if min_pct:
        visible_discounts = visible_discounts.filter(percentage__gte=min_pct)

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

    # Apply area filter — exact match on a chip; case-insensitive search via `q` still works.
    if selected_area:
        places_qs = places_qs.filter(area=selected_area)

    places_qs = places_qs.prefetch_related(
        Prefetch("discounts", queryset=visible_discounts, to_attr="visible_discounts")
    )

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
        # popularity = total live offers on this place + breadth of distinct
        # programs covering it. Two complementary signals: a brand with many
        # offers in one program ranks similarly to one offer across many
        # programs (both are "well-covered" venues from the user's POV).
        place.popularity = place.offer_count + len(seen)

    active_filter_count = (
        len(selected_programs)
        + len(selected_experiences)
        + len(selected_types)
        + (1 if only_gems else 0)
        + (1 if selected_area else 0)
        + (1 if min_pct else 0)
    )
    show_top_rail = not (q or active_filter_count)

    if show_top_rail:
        # Tiebreak by name so the order is stable when popularity ties.
        places.sort(key=lambda p: (-p.popularity, p.name.lower()))
    else:
        places.sort(key=lambda p: p.name.lower())

    context = {
        "places": places,
        "show_top_rail": show_top_rail,
        "selected": {
            "q": q,
            "programs": selected_programs,
            "experiences": selected_experiences,
            "types": selected_types,
            "area": selected_area,
            "gems": only_gems,
            "min_pct": min_pct,
        },
        # Playbook is excluded: it's a venue-discovery app, not a discount
        # program — its "Highlights" (Ladies Night, Afternoon Tea, …) were
        # marketing events, not offers. Removed from the filter panel so the
        # checkbox doesn't return zero results.
        "all_programs": [(v, lbl) for v, lbl in DiscountProgram.choices if v != "playbook"],
        "all_experiences": list(Experience.objects.filter(is_active=True).order_by("sort_order", "label")),
        "all_types": list(DiscountType.choices),
        "all_areas": _top_areas(),
        "min_pct_options": list(_MIN_PCT_OPTIONS),
        "active_filter_count": active_filter_count,
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
