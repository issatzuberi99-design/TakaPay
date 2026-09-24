from django.contrib import admin

from .models import Wallet, WalletTransaction


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "created_at", "updated_at")
    search_fields = ("user__username", "user__email", "user__phone_number")
    ordering = ("user__username",)
    list_select_related = ("user",)
    readonly_fields = ("user", "balance", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "wallet_user", "transaction_type", "amount", "description", "reward_basis", "collection", "created_at",
    )
    list_filter = ("transaction_type", "created_at")
    search_fields = (
        "wallet__user__username", "wallet__user__email", "wallet__user__phone_number",
        "reference", "description",
    )
    date_hierarchy = "created_at"
    list_select_related = ("wallet__user", "collection")
    readonly_fields = (
        "wallet", "transaction_type", "amount", "description", "reference", "collection",
        "collection_reward_material", "collection_reward_quantity", "collection_reward_unit",
        "collection_reward_rate", "created_at",
    )

    @admin.display(description="Wallet / user", ordering="wallet__user__username")
    def wallet_user(self, obj):
        return obj.wallet.user

    @admin.display(description="Reward basis")
    def reward_basis(self, obj):
        if obj.collection_reward_unit:
            return f"{obj.collection_reward_quantity} {obj.get_collection_reward_unit_display()} × {obj.collection_reward_rate} · {obj.collection_reward_material}"
        return "—"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
