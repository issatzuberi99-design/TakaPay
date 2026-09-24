from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.accounts.decorators import role_required
from apps.accounts.models import User

from .models import Wallet, WalletTransaction


@role_required(User.Role.CUSTOMER)
def wallet_view(request):
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    if created:
        messages.info(request, "Your wallet has been created.")
    transactions = wallet.transactions.select_related().order_by("-created_at")
    return render(request, "wallet/wallet.html", {"wallet": wallet, "transactions": transactions})
