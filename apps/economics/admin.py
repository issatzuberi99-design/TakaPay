from django.contrib import admin

from .models import (
    CollectorBonus,
    CollectorPayout,
    CollectorWallet,
    CollectorWalletTransaction,
    EconomicPolicy,
    EconomicSettlement,
    EconomicSetting,
    MaterialRate,
)


@admin.register(EconomicSetting)
class EconomicSettingAdmin(admin.ModelAdmin):
    list_display = ("customer_cashout_min_tokens", "collector_payout_min_tzs", "updated_at")


@admin.register(EconomicPolicy)
class EconomicPolicyAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "customer_percent", "collector_percent", "operations_percent", "active", "effective_from")
    list_filter = ("active", "category")
    readonly_fields = ("created_at", "updated_at")


@admin.register(MaterialRate)
class MaterialRateAdmin(admin.ModelAdmin):
    list_display = ("category", "rate_per_unit", "currency", "active", "effective_from")
    list_filter = ("active", "currency")


@admin.register(CollectorBonus)
class CollectorBonusAdmin(admin.ModelAdmin):
    list_display = ("name", "amount", "active", "effective_from", "effective_until")
    list_filter = ("active",)


@admin.register(CollectorWallet)
class CollectorWalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "created_at", "updated_at")
    readonly_fields = ("user", "balance", "created_at", "updated_at")
    search_fields = ("user__username", "user__email")

    def has_add_permission(self, request):
        return False


@admin.register(CollectorWalletTransaction)
class CollectorWalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("collector_wallet", "transaction_type", "amount", "collection", "created_at")
    list_filter = ("transaction_type", "created_at")
    readonly_fields = ("collector_wallet", "transaction_type", "amount", "description", "collection", "payout", "reference", "created_at")

    def has_add_permission(self, request):
        return False


@admin.register(EconomicSettlement)
class EconomicSettlementAdmin(admin.ModelAdmin):
    list_display = ("collection", "material", "verified_quantity", "gross_value", "customer_tokens", "total_collector_earning", "operations_allocation", "settled_at")
    list_filter = ("category", "settled_at")
    readonly_fields = tuple(field.name for field in EconomicSettlement._meta.fields)

    def has_add_permission(self, request):
        return False


@admin.register(CollectorPayout)
class CollectorPayoutAdmin(admin.ModelAdmin):
    list_display = ("collector", "amount", "currency", "status", "requested_at", "processed_at")
    list_filter = ("status", "currency", "requested_at")
    search_fields = ("collector__username", "collector__email", "provider_name")
    readonly_fields = ("collector", "amount", "currency", "payout_method", "provider_name", "destination", "requested_at", "processed_at", "processed_by")
