from django.contrib import admin

from .models import WasteCategory, WasteReport


@admin.register(WasteCategory)
class WasteCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "token_rate_per_kg", "active", "created_at", "updated_at")
    list_filter = ("active",)
    search_fields = ("name",)


@admin.register(WasteReport)
class WasteReportAdmin(admin.ModelAdmin):
    list_display = (
        "customer",
        "category",
        "estimated_weight",
        "weight_unit",
        "latitude",
        "longitude",
        "status",
        "created_at",
    )
    list_filter = ("status", "category", "created_at")
    search_fields = ("customer__username", "customer__email", "description")
