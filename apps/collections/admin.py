from django.contrib import admin

from .models import CollectionRequest


@admin.register(CollectionRequest)
class CollectionRequestAdmin(admin.ModelAdmin):
    list_display = (
        "waste_report",
        "customer",
        "collector",
        "status",
        "estimated_weight",
        "actual_weight",
        "proof_photo",
        "accepted_at",
        "completed_at",
        "created_at",
    )
    list_filter = ("status", "collector", "created_at")
    search_fields = (
        "waste_report__customer__username",
        "waste_report__customer__email",
        "collector__username",
        "notes",
    )
    readonly_fields = ("created_at", "updated_at", "accepted_at", "completed_at")

    def customer(self, obj):
        return obj.waste_report.customer

    customer.short_description = "Customer"

    def estimated_weight(self, obj):
        return f"{obj.waste_report.estimated_weight} {obj.waste_report.get_weight_unit_display()}"

    estimated_weight.short_description = "Estimated weight"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("waste_report__customer", "collector")
