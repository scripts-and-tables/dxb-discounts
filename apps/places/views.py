from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from apps.accounts.selectors import attach_favorited
from apps.discounts.models import Discount, DiscountProgram

from .models import Category, Place


# Map source_program slug → Tailwind background class for the outer group
# header. Mirrors the per-program palette in templates/places/_program_tile.html.
_PROGRAM_HEADER_CLASS = {
    "fazaa": "bg-red-700",
    "esaad": "bg-teal-800",
    "in_house": "bg-amber-700",
    "entertainer": "bg-blue-700",
    "zomato": "bg-rose-600",
    "repeat": "bg-violet-700",
    "playbook": "bg-cyan-700",
    "elite_club": "bg-stone-700",
    "supper_club": "bg-emerald-700",
    "emirates_platinum": "bg-zinc-800",
    "shukran": "bg-orange-700",
    "share_rewards": "bg-indigo-700",
    "emirates_skywards": "bg-sky-700",
    "atlantis_circle": "bg-slate-900",
    "u_by_emaar": "bg-purple-700",
    "al_futtaim_blue": "bg-blue-700",
    "referral": "bg-rose-700",
}


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
    if not request.user.is_authenticated:
        qs = qs.filter(is_members_only=False)

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
    if place.is_members_only and not request.user.is_authenticated:
        raise Http404
    discounts_qs = (
        Discount.objects
        .live()
        .filter(place=place)
        .order_by("-is_featured", "-created_at")
    )
    if not request.user.is_authenticated:
        discounts_qs = discounts_qs.filter(is_members_only=False)
    discounts = attach_favorited(discounts_qs, request.user)

    # Group by source_program. In-house first; remaining groups by descending
    # offer count (so the program with the most offers shows up high in the list).
    by_program: dict[str, list[Discount]] = {}
    label_for: dict[str, str] = dict(DiscountProgram.choices)
    for d in discounts:
        by_program.setdefault(d.source_program or "", []).append(d)
    ordered_keys = []
    if "in_house" in by_program:
        ordered_keys.append("in_house")
    rest = [k for k in by_program if k != "in_house"]
    rest.sort(key=lambda k: -len(by_program[k]))
    ordered_keys += rest
    discount_groups = [
        {
            "slug": k,
            "label": label_for.get(k) or "Other offer",
            "header_class": _PROGRAM_HEADER_CLASS.get(k, "bg-slate-700"),
            "discounts": by_program[k],
        }
        for k in ordered_keys
    ]

    return render(request, "places/detail.html", {
        "place": place,
        "discount_groups": discount_groups,
    })
