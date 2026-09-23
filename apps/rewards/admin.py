from django.contrib import admin

from .models import Reward


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ("name", "token_cost", "available", "inventory", "created_at")
    list_filter = ("available",)
    search_fields = ("name",)
