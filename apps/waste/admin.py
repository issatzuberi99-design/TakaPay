from django.contrib import admin
from django.utils.html import format_html

from .models import WasteCategory, WasteReport


@admin.register(WasteCategory)
class WasteCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "reward_unit", "token_rate", "active", "created_at", "updated_at")
    list_filter = ("active",)
    search_fields = ("name",)
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(WasteReport)
class WasteReportAdmin(admin.ModelAdmin):
    list_display = (
        "customer", "category", "estimated_weight", "weight_unit", "status", "created_at", "photo_link",
    )
    list_filter = ("status", "category", "created_at")
    search_fields = (
        "customer__username", "customer__email", "customer__phone_number", "description",
    )
    date_hierarchy = "created_at"
    list_select_related = ("customer", "category")
    readonly_fields = ("created_at", "updated_at", "photo_link")
    fields = (
        "customer", "category", "description", "estimated_weight", "weight_unit", "status",
        "latitude", "longitude", "location_accuracy", "photo", "photo_link", "created_at", "updated_at",
    )

    @admin.display(description="Photo")
    def photo_link(self, obj):
        if not obj.photo:
            return "—"
        return format_html('<a href="{}" target="_blank" rel="noopener">View photo</a>', obj.photo.url)
