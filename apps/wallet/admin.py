from django.contrib import admin

from .models import Wallet, WalletTransaction


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "created_at", "updated_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("balance",)


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("wallet", "transaction_type", "amount", "description", "reference", "collection", "created_at")
    list_filter = ("transaction_type", "created_at")
    search_fields = ("wallet__user__username", "reference", "description")
