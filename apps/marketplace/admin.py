from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect

from .models import BuyerRequest, MarketplaceMaterial


@admin.register(MarketplaceMaterial)
class MarketplaceMaterialAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "available_quantity", "unit", "price_per_unit", "active", "created_at")
    list_filter = ("active", "unit", "category")
    search_fields = ("name", "description")


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
        if cleaned_data["status"] != current.status and cleaned_data["status"] not in allowed_transitions.get(current.status, set()):
            self.add_error("status", f"A {current.get_status_display()} request cannot be moved to that status.")
        return cleaned_data


@admin.register(BuyerRequest)
class BuyerRequestAdmin(admin.ModelAdmin):
    form = BuyerRequestAdminForm
    list_display = ("id", "buyer_name", "material_name", "requested_quantity", "unit", "status", "requested_at")
    list_filter = ("status", "unit", "requested_at")
    search_fields = ("buyer_name", "company_name", "phone_number", "email", "material_name")
    readonly_fields = (
        "buyer_name", "company_name", "phone_number", "email", "location", "material",
        "material_name", "requested_quantity", "unit", "price_per_unit", "message",
        "requested_at", "processed_at", "processed_by",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("material", "processed_by")

    def save_model(self, request, obj, form, change):
        if change:
            original = BuyerRequest.objects.get(pk=obj.pk)
            if original.status != obj.status:
                obj.transition_to(obj.status, request.user, obj.admin_notes)
                return
        super().save_model(request, obj, form, change)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except ValidationError as error:
            # The inventory check can change between form validation and save.
            messages.error(request, error.message)
            return HttpResponseRedirect(request.path)
