from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import CashOutRate, CashOutRequest


@admin.register(CashOutRate)
class CashOutRateAdmin(admin.ModelAdmin):
    list_display = ("tokens_per_money_unit", "money_amount", "currency", "active", "created_at")
    list_filter = ("active", "currency")


@admin.register(CashOutRequest)
class CashOutRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "token_amount", "money_amount", "currency", "payout_method", "status", "requested_at")
    list_filter = ("status", "payout_method", "currency", "requested_at")
    search_fields = ("customer__username", "customer__email", "provider_name", "phone_number", "account_number")
    readonly_fields = ("customer", "token_amount", "money_amount", "currency", "tokens_per_money_unit", "payout_method", "provider_name", "phone_number", "account_number", "requested_at", "processed_at", "processed_by")

    def save_model(self, request, obj, form, change):
        if change:
            original = CashOutRequest.objects.get(pk=obj.pk)
            if original.status != obj.status:
                try:
                    obj.transition_to(obj.status, request.user, obj.admin_notes)
                except ValidationError as error:
                    form.add_error("status", error.message)
                    messages.error(request, error.message)
                return
        super().save_model(request, obj, form, change)