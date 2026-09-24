from django.contrib import admin

from .models import Reward, RewardRedemption


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ("name", "token_cost", "active", "inventory", "created_at", "updated_at")
    list_filter = ("active",)
    search_fields = ("name", "description")


@admin.register(RewardRedemption)
class RewardRedemptionAdmin(admin.ModelAdmin):
    list_display = ("customer", "reward", "token_amount", "status", "created_at")
    list_filter = ("status", "created_at", "reward")
    search_fields = ("customer__username", "customer__email", "reward__name")
    readonly_fields = ("customer", "reward", "token_amount", "created_at", "updated_at")
