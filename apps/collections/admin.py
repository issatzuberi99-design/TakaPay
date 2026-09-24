from django.contrib import admin

from .models import CollectionRequest


@admin.register(CollectionRequest)
class CollectionRequestAdmin(admin.ModelAdmin):
    list_display = (
        "waste_report", "customer", "collector", "status", "estimated_quantity", "actual_quantity",
        "proof_photo", "accepted_at", "completed_at",
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
        "waste_report", "collector", "status", "actual_weight", "actual_piece_count", "weight_unit", "proof_photo",
        "accepted_at", "completed_at", "created_at", "updated_at",
    )

    @admin.display(description="Customer", ordering="waste_report__customer__username")
    def customer(self, obj):
        return obj.waste_report.customer

    @admin.display(description="Estimated quantity")
    def estimated_quantity(self, obj):
        report = obj.waste_report
        if report.category.reward_unit == "piece":
            return f"{report.estimated_piece_count} pieces"
        return f"{report.estimated_weight} {report.get_weight_unit_display()}"

    @admin.display(description="Verified quantity")
    def actual_quantity(self, obj):
        if obj.actual_piece_count is not None:
            return f"{obj.actual_piece_count} pieces"
        if obj.actual_weight is not None:
            return f"{obj.actual_weight} {obj.get_weight_unit_display()}"
        return "—"
