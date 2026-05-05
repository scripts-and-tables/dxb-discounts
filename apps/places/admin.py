from django.contrib import admin

from apps.discounts.models import Discount

from .models import Place


class DiscountInline(admin.TabularInline):
    model = Discount
    extra = 0
    fields = ("title", "discount_type", "percentage", "fixed_price_aed", "promo_code", "is_active", "is_featured", "valid_until")
    show_change_link = True


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "area", "is_published", "discount_count", "updated_at")
    list_filter = ("category", "is_published", "area")
    search_fields = ("name", "area", "address")
    prepopulated_fields = {"slug": ("name",)}
    list_per_page = 50
    inlines = [DiscountInline]

    @admin.display(description="Discounts")
    def discount_count(self, obj: Place) -> int:
        return obj.discounts.count()
