from django.contrib import admin

from apps.discounts.models import Discount

from .models import Experience, Place


class DiscountInline(admin.TabularInline):
    model = Discount
    extra = 0
    fields = ("title", "discount_type", "percentage", "fixed_price_aed", "promo_code", "is_active", "is_featured", "valid_until")
    show_change_link = True


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "area", "is_published", "is_members_only", "discount_count", "updated_at")
    list_filter = ("category", "is_published", "is_members_only", "area", "experiences")
    search_fields = ("name", "area", "address")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("experiences",)
    list_per_page = 50
    inlines = [DiscountInline]

    @admin.display(description="Discounts")
    def discount_count(self, obj: Place) -> int:
        return obj.discounts.count()


@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ("label", "slug", "sort_order", "is_active", "place_count")
    list_filter = ("is_active",)
    search_fields = ("label", "slug")
    prepopulated_fields = {"slug": ("label",)}
    list_editable = ("sort_order", "is_active")

    @admin.display(description="Places")
    def place_count(self, obj: Experience) -> int:
        return obj.places.count()
