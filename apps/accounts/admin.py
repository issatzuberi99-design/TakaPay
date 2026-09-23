from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CollectorProfile, User


@admin.register(User)
class TakaPayUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("TakaPay details", {"fields": ("role", "phone_number", "collector_verification_status")}),
    )
    list_display = ("username", "email", "role", "collector_verification_status", "is_staff")
    list_filter = ("role", "collector_verification_status", "is_staff")


@admin.register(CollectorProfile)
class CollectorProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "verification_status", "identification_reference", "updated_at")
    list_filter = ("verification_status",)
    search_fields = ("user__username", "user__email", "identification_reference")

    def save_model(self, request, obj, form, change):
        obj.user.collector_verification_status = obj.verification_status
        obj.user.save(update_fields=("collector_verification_status",))
        super().save_model(request, obj, form, change)
