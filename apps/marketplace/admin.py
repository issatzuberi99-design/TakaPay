from django.contrib import admin

from .models import BuyerRequest, MarketplaceMaterial


@admin.register(MarketplaceMaterial)
class MarketplaceMaterialAdmin(admin.ModelAdmin):
    list_display = ("name", "available_quantity", "unit", "active", "created_at")
    list_filter = ("active",)
    search_fields = ("name",)


@admin.register(BuyerRequest)
class BuyerRequestAdmin(admin.ModelAdmin):
    list_display = ("buyer_name", "requested_material", "requested_quantity", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("buyer_name", "company", "phone", "email")
