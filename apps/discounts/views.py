from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from apps.accounts.selectors import attach_favorited
from apps.places.models import Category, Place

from .models import Discount, DiscountType


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
        "discount_types": DiscountType.choices,
        "areas": [a for a in areas if a],
    }


def _gate_members_only(qs, user):
    """Filter members-only items out for anonymous users."""
    if user.is_authenticated:
        return qs
    return qs.filter(is_members_only=False, place__is_members_only=False)


@require_GET
def discount_list(request):
    qs = Discount.objects.live().select_related("place")
    qs = _gate_members_only(qs, request.user)

    category = request.GET.get("category", "").strip()
    area = request.GET.get("area", "").strip()
    discount_type = request.GET.get("type", "").strip()
    q = request.GET.get("q", "").strip()

    if category:
        qs = qs.filter(place__category=category)
    if area:
        qs = qs.filter(place__area__iexact=area)
    if discount_type:
        qs = qs.filter(discount_type=discount_type)
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(place__name__icontains=q)
            | Q(place__area__icontains=q)
        )

    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
    page.object_list = attach_favorited(page.object_list, request.user)

    selected = {
        "category": category,
        "area": area,
        "type": discount_type,
        "q": q,
    }

    template = "discounts/_results.html" if request.headers.get("HX-Request") else "discounts/list.html"
    return render(request, template, {
        "page_obj": page,
        "selected": selected,
        **_filter_choices(),
    })


@require_GET
def discount_detail(request, slug: str):
    discount = get_object_or_404(
        Discount.objects.select_related("place"),
        slug=slug,
        is_active=True,
        place__is_published=True,
    )
    if not request.user.is_authenticated and (discount.is_members_only or discount.place.is_members_only):
        raise Http404
    related = (
        Discount.objects
        .live()
        .filter(place=discount.place)
        .exclude(pk=discount.pk)
        .order_by("-is_featured", "-created_at")[:6]
    )
    related = attach_favorited(related, request.user)
    attach_favorited([discount], request.user)
    return render(request, "discounts/detail.html", {
        "discount": discount,
        "related": related,
    })
