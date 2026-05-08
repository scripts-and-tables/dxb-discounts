from django.contrib import admin

from .models import Discount, Program


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = ("title", "place", "discount_type", "source_program", "headline", "is_active", "is_featured", "is_gem", "is_members_only", "valid_until", "updated_at")
    list_filter = ("discount_type", "source_program", "is_active", "is_featured", "is_gem", "is_members_only", "place__category")
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
        ("Source, validity & visibility", {
            "fields": ("source_program", "valid_from", "valid_until", "is_active", "is_featured", "is_gem", "is_members_only"),
        }),
    )


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "cost_summary", "eligibility", "is_published", "sort_order", "updated_at")
    list_filter = ("is_published",)
    search_fields = ("name", "slug", "short_description", "description")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("sort_order", "is_published")
    fieldsets = (
        (None, {"fields": ("name", "slug", "short_description", "description")}),
        ("Links & meta", {"fields": ("official_url", "cost_summary", "eligibility")}),
        ("Visibility", {"fields": ("is_published", "sort_order")}),
    )
