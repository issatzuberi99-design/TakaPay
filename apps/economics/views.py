from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render

from apps.accounts.decorators import approved_collector_required

from .forms import CollectorPayoutForm
from .models import EconomicSetting
from .services import collector_wallet_for, request_collector_payout


@approved_collector_required
def collector_payout_create(request):
    wallet = collector_wallet_for(request.user)
    form = CollectorPayoutForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            payout = request_collector_payout(
                collector=request.user,
                amount=form.cleaned_data["amount"],
                payout_method=form.cleaned_data["payout_method"],
                provider_name=form.cleaned_data["provider_name"],
                destination=form.cleaned_data["destination"],
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, f"Collector payout request #{payout.pk} submitted.")
            return redirect("collector_payout_create")
    return render(request, "economics/collector_payout.html", {
        "form": form, "wallet": wallet, "settings": EconomicSetting.current(),
    })
