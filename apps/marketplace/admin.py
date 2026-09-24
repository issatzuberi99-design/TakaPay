from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect

from .models import BuyerRequest, MarketplaceMaterial
from .services import transition_buyer_request


@admin.register(MarketplaceMaterial)
class MarketplaceMaterialAdmin(admin.ModelAdmin):
    list_display = (
        "name", "category", "available_quantity", "unit", "price_per_unit", "active", "updated_at",
    )
    list_filter = ("active", "unit", "category")
    search_fields = ("name", "description")
    ordering = ("-updated_at", "name")
    list_select_related = ("category",)


class BuyerRequestAdminForm(forms.ModelForm):
    class Meta:
        model = BuyerRequest
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        if not self.instance.pk or "status" not in cleaned_data:
            return cleaned_data

        current = BuyerRequest.objects.get(pk=self.instance.pk)
        allowed_transitions = {
            BuyerRequest.Status.PENDING: {
                BuyerRequest.Status.PROCESSING,
                BuyerRequest.Status.REJECTED,
                BuyerRequest.Status.CANCELLED,
            },
            BuyerRequest.Status.PROCESSING: {
                BuyerRequest.Status.COMPLETED,
                BuyerRequest.Status.REJECTED,
                BuyerRequest.Status.CANCELLED,
            },
        }
        new_status = cleaned_data["status"]
        if new_status != current.status and new_status not in allowed_transitions.get(current.status, set()):
            self.add_error("status", f"A {current.get_status_display()} request cannot be moved to that status.")
        return cleaned_data


@admin.register(BuyerRequest)
class BuyerRequestAdmin(admin.ModelAdmin):
    form = BuyerRequestAdminForm
    list_display = (
        "id", "material_display", "buyer_name", "company_name", "requested_quantity", "unit",
        "status", "requested_at", "processed_at", "processed_by",
    )
    list_filter = ("status", "unit", "requested_at", "processed_at")
    search_fields = (
        "buyer_name", "company_name", "phone_number", "email", "material_name", "material__name",
    )
    date_hierarchy = "requested_at"
    list_select_related = ("material", "processed_by")
    readonly_fields = (
        "buyer_name", "company_name", "phone_number", "email", "location", "material",
        "material_name", "requested_quantity", "unit", "price_per_unit", "message",
        "requested_at", "processed_at", "processed_by",
    )

    @admin.display(description="Material", ordering="material_name")
    def material_display(self, obj):
        return obj.material_name or obj.material.name

    def save_model(self, request, obj, form, change):
        if change:
            original = BuyerRequest.objects.get(pk=obj.pk)
            if original.status != obj.status:
                transition_buyer_request(obj, obj.status, request.user, obj.admin_notes)
                return
        super().save_model(request, obj, form, change)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except ValidationError as error:
            # The stock check can change between form validation and the database save.
            messages.error(request, error.message)
            return HttpResponseRedirect(request.path)
