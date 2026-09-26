from django.contrib import messages
from django.core.paginator import Paginator
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
    page_obj = Paginator(wallet.transactions.order_by("-created_at"), 20).get_page(request.GET.get("page"))
    return render(request, "wallet/wallet.html", {"wallet": wallet, "transactions": page_obj.object_list, "page_obj": page_obj})
