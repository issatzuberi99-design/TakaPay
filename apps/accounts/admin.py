from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib import messages
from django.db import transaction

from .models import CollectorProfile, User
from .services import set_collector_verification
from apps.cashout.models import CashOutRequest
from apps.economics.models import CollectorPayout
from apps.wallet.models import Wallet


@admin.register(User)
class TakaPayUserAdmin(UserAdmin):
    actions = ("deactivate_users", "anonymize_users")
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

    @admin.action(description="Deactivate selected users (preserve wallet history)")
    def deactivate_users(self, request, queryset):
        updated = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, f"{updated} user(s) deactivated. Wallet and transaction history was preserved.", messages.SUCCESS)

    @admin.action(description="Anonymize selected users (preserve all data)")
    def anonymize_users(self, request, queryset):
        anonymized = 0
        with transaction.atomic():
            for user in queryset.select_for_update():
                user_id = user.pk
                CollectorProfile.objects.filter(user=user).update(
                    identification_reference=f"ANON-{user_id}",
                    address="Anonymized",
                )
                CashOutRequest.objects.filter(customer=user).update(
                    phone_number="",
                    account_number="",
                    provider_name="Anonymized",
                )
                CollectorPayout.objects.filter(collector=user).update(
                    destination="Anonymized",
                    provider_name="Anonymized",
                )
                user.username = f"deleted-user-{user_id}"
                user.first_name = ""
                user.last_name = ""
                user.email = ""
                user.phone_number = ""
                user.is_active = False
                user.set_unusable_password()
                user.save(update_fields=(
                    "username", "first_name", "last_name", "email", "phone_number",
                    "is_active", "password",
                ))
                anonymized += 1
        self.message_user(request, f"{anonymized} user(s) anonymized. Wallet and transaction history was preserved.", messages.SUCCESS)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and Wallet.objects.filter(user=obj).exists():
            return False
        return super().has_delete_permission(request, obj)


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

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        set_collector_verification(obj.pk, obj.verification_status)
