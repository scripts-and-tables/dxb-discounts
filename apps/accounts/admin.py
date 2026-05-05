from django.contrib import admin

from .models import EmailCode, Favorite


@admin.register(EmailCode)
class EmailCodeAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "code", "attempts", "expires_at", "used_at", "created_at")
    list_filter = ("purpose",)
    search_fields = ("user__email", "user__username", "code")
    readonly_fields = ("user", "purpose", "code", "attempts", "expires_at", "used_at", "created_at")


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "discount", "created_at")
    search_fields = ("user__email", "user__username", "discount__title")
    autocomplete_fields = ("user", "discount")
