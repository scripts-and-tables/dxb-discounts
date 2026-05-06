from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.discounts.models import Discount
from apps.places.models import Place


@require_GET
def home(request):
    visible_discounts = Discount.objects.live().select_related("place")
    if not request.user.is_authenticated:
        visible_discounts = visible_discounts.filter(
            is_members_only=False,
            place__is_members_only=False,
        )

    place_ids = list(visible_discounts.values_list("place_id", flat=True).distinct())
    places_qs = Place.objects.filter(id__in=place_ids, is_published=True)
    if not request.user.is_authenticated:
        places_qs = places_qs.filter(is_members_only=False)
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

    return render(request, "pages/home.html", {"places": places})


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
