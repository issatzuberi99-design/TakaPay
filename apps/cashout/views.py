from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render

from apps.accounts.decorators import role_required
from apps.accounts.models import User
from apps.wallet.models import Wallet, WalletTransaction
from apps.economics.models import EconomicSetting

from .forms import CashOutRequestForm
from .models import CashOutRate, CashOutRequest


@role_required(User.Role.CUSTOMER)
def cashout_create(request):
    rate = CashOutRate.objects.filter(active=True).first()
    wallet = Wallet.objects.get_or_create(user=request.user)[0]
    if request.method == "POST":
        form = CashOutRequestForm(request.POST)
        if form.is_valid() and rate:
            cashout = None
            try:
                with transaction.atomic():
                    wallet = Wallet.objects.select_for_update().get(user=request.user)
                    locked_rate = CashOutRate.objects.select_for_update().get(pk=rate.pk, active=True)
                    token_amount = form.cleaned_data["token_amount"]
                    minimum_tokens = EconomicSetting.current().customer_cashout_min_tokens
                    if token_amount < minimum_tokens:
                        form.add_error("token_amount", f"Cash-outs require at least {minimum_tokens} Tokens.")
                    elif wallet.balance < token_amount:
                        form.add_error("token_amount", "You do not have enough TakaPay Tokens.")
                    else:
                        cashout = form.save(commit=False)
                        cashout.customer = request.user
                        cashout.money_amount = CashOutRequest.calculate_money_amount(token_amount, locked_rate)
                        cashout.currency = locked_rate.currency
                        cashout.tokens_per_money_unit = locked_rate.tokens_per_money_unit
                        cashout.full_clean()
                        cashout.save()
                        WalletTransaction.objects.create(
                            wallet=wallet,
                            transaction_type=WalletTransaction.TransactionType.CASHOUT,
                            amount=-token_amount,
                            description=f"Cash-out request #{cashout.pk}",
                            reference=f"cashout-{cashout.pk}",
                        )
            except (CashOutRate.DoesNotExist, Wallet.DoesNotExist):
                form.add_error(None, "Cash-out is temporarily unavailable.")
            else:
                if cashout is not None:
                    messages.success(request, "Your cash-out request has been submitted.")
                    return redirect("cashout_history")
        elif not rate:
            form.add_error(None, "Cash-out is temporarily unavailable.")
    else:
        form = CashOutRequestForm()
    return render(request, "cashout/cashout_form.html", {"form": form, "wallet": wallet, "rate": rate})


@role_required(User.Role.CUSTOMER)
def cashout_history(request):
    requests = CashOutRequest.objects.filter(customer=request.user).select_related("processed_by")
    return render(request, "cashout/cashout_history.html", {"cashout_requests": requests})