from django.contrib import admin

from .models import Discount


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = ("title", "place", "discount_type", "headline", "is_active", "is_featured", "is_members_only", "valid_until", "updated_at")
    list_filter = ("discount_type", "is_active", "is_featured", "is_members_only", "place__category")
    search_fields = ("title", "description", "place__name", "place__area")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("place",)
    list_per_page = 50
    fieldsets = (
        (None, {
            "fields": ("place", "title", "slug", "description", "terms"),
        }),
        ("Deal", {
            "fields": ("discount_type", "percentage", "fixed_price_aed", "promo_code"),
        }),
        ("Validity & visibility", {
            "fields": ("valid_from", "valid_until", "is_active", "is_featured", "is_members_only"),
        }),
    )
