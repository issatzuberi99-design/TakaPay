from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db import transaction

from .models import CollectorProfile, User


@admin.register(User)
class TakaPayUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("TakaPay details", {"fields": ("role", "phone_number", "collector_verification_status")}),
    )
    readonly_fields = UserAdmin.readonly_fields + ("date_joined",)
    list_display = (
        "username", "email", "phone_number", "role", "is_active", "is_staff",
        "collector_verification_status",
    )
    list_filter = ("role", "is_active", "collector_verification_status", "is_staff")
    search_fields = ("username", "email", "phone_number", "first_name", "last_name")
    ordering = ("username",)


@admin.register(CollectorProfile)
class CollectorProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user", "user_email", "verification_status", "identification_reference", "created_at", "updated_at",
    )
    list_filter = ("verification_status", "created_at")
    search_fields = (
        "user__username", "user__email", "user__phone_number", "identification_reference",
    )
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    list_select_related = ("user",)

    @admin.display(description="Email", ordering="user__email")
    def user_email(self, obj):
        return obj.user.email

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.user.collector_verification_status = obj.verification_status
        obj.user.save(update_fields=("collector_verification_status",))
