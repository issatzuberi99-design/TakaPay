from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import User

from .models import Wallet


@receiver(post_save, sender=User)
def create_customer_wallet(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.role == User.Role.CUSTOMER:
        Wallet.objects.get_or_create(user=instance)
