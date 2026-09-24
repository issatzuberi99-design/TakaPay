from django.contrib import admin

from .models import CollectionRequest


@admin.register(CollectionRequest)
class CollectionRequestAdmin(admin.ModelAdmin):
    list_display = (
        "waste_report", "customer", "collector", "status", "estimated_weight", "actual_weight",
        "weight_unit", "proof_photo", "accepted_at", "completed_at",
    )
    list_filter = ("status", "created_at", "accepted_at", "completed_at")
    search_fields = (
        "waste_report__customer__username", "waste_report__customer__email",
        "waste_report__customer__phone_number", "collector__username", "collector__email",
        "collector__phone_number", "notes",
    )
    date_hierarchy = "created_at"
    list_select_related = ("waste_report__customer", "waste_report__category", "collector")
    # Collection completion and its wallet reward must go through the existing workflow.
    readonly_fields = (
        "waste_report", "collector", "status", "actual_weight", "weight_unit", "proof_photo",
        "accepted_at", "completed_at", "created_at", "updated_at",
    )

    @admin.display(description="Customer", ordering="waste_report__customer__username")
    def customer(self, obj):
        return obj.waste_report.customer

    @admin.display(description="Estimated weight")
    def estimated_weight(self, obj):
        return f"{obj.waste_report.estimated_weight} {obj.waste_report.get_weight_unit_display()}"
