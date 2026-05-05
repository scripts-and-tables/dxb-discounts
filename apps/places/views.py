from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from apps.discounts.models import Discount

from .models import Category, Place


PAGE_SIZE = 24


def _filter_choices():
    areas = (
        Place.objects
        .filter(is_published=True)
        .values_list("area", flat=True)
        .distinct()
        .order_by("area")
    )
    return {
        "categories": Category.choices,
        "areas": [a for a in areas if a],
    }


@require_GET
def place_list(request):
    qs = (
        Place.objects
        .filter(is_published=True)
        .annotate(live_discount_count=Count(
            "discounts",
            filter=Q(discounts__is_active=True),
        ))
    )

    category = request.GET.get("category", "").strip()
    area = request.GET.get("area", "").strip()
    q = request.GET.get("q", "").strip()

    if category:
        qs = qs.filter(category=category)
    if area:
        qs = qs.filter(area__iexact=area)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(area__icontains=q))

    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))

    context = {
        "page_obj": page,
        "selected": {"category": category, "area": area, "q": q},
        **_filter_choices(),
    }
    return render(request, "places/list.html", context)


@require_GET
def place_detail(request, slug: str):
    place = get_object_or_404(Place, slug=slug, is_published=True)
    discounts = (
        Discount.objects
        .live()
        .filter(place=place)
        .order_by("-is_featured", "-created_at")
    )
    return render(request, "places/detail.html", {
        "place": place,
        "discounts": discounts,
    })
