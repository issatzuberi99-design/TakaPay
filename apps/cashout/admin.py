from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect

from .models import CashOutRate, CashOutRequest


@admin.register(CashOutRate)
class CashOutRateAdmin(admin.ModelAdmin):
    list_display = ("tokens_per_money_unit", "money_amount", "currency", "active", "created_at", "updated_at")
    list_filter = ("active", "currency")
    ordering = ("-active", "-created_at")
    readonly_fields = ("created_at", "updated_at")


class CashOutRequestAdminForm(forms.ModelForm):
    class Meta:
        model = CashOutRequest
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        if not self.instance.pk or "status" not in cleaned_data:
            return cleaned_data

        current = CashOutRequest.objects.get(pk=self.instance.pk)
        allowed_transitions = {
            CashOutRequest.Status.PENDING: {
                CashOutRequest.Status.PROCESSING,
                CashOutRequest.Status.REJECTED,
            },
            CashOutRequest.Status.PROCESSING: {
                CashOutRequest.Status.COMPLETED,
                CashOutRequest.Status.REJECTED,
            },
        }
        new_status = cleaned_data["status"]
        if new_status != current.status and new_status not in allowed_transitions.get(current.status, set()):
            self.add_error("status", f"A {current.get_status_display()} request cannot be moved to that status.")
        return cleaned_data


@admin.register(CashOutRequest)
class CashOutRequestAdmin(admin.ModelAdmin):
    form = CashOutRequestAdminForm
    list_display = (
        "id", "customer", "token_amount", "money_amount", "currency", "conversion_rate",
        "payout_method", "provider_name", "status", "requested_at", "processed_at", "processed_by",
    )
    list_filter = ("status", "payout_method", "currency", "requested_at", "processed_at")
    search_fields = ("customer__username", "customer__email", "customer__phone_number", "provider_name")
    date_hierarchy = "requested_at"
    list_select_related = ("customer", "processed_by")
    readonly_fields = (
        "customer", "token_amount", "money_amount", "currency", "tokens_per_money_unit",
        "payout_method", "provider_name", "phone_number", "account_number", "requested_at",
        "processed_at", "processed_by",
    )

    @admin.display(description="Conversion rate", ordering="tokens_per_money_unit")
    def conversion_rate(self, obj):
        return obj.tokens_per_money_unit

    def save_model(self, request, obj, form, change):
        if change:
            original = CashOutRequest.objects.get(pk=obj.pk)
            if original.status != obj.status:
                obj.transition_to(obj.status, request.user, obj.admin_notes)
                return
        super().save_model(request, obj, form, change)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except ValidationError as error:
            messages.error(request, error.message)
            return HttpResponseRedirect(request.path)
