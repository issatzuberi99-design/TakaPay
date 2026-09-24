from django import forms

from .models import CashOutRequest


class CashOutRequestForm(forms.ModelForm):
    class Meta:
        model = CashOutRequest
        fields = ("token_amount", "payout_method", "provider_name", "phone_number", "account_number")
        widgets = {
            "token_amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "phone_number": forms.TextInput(attrs={"autocomplete": "tel"}),
            "account_number": forms.TextInput(attrs={"autocomplete": "off"}),
        }

    def clean_provider_name(self):
        value = self.cleaned_data["provider_name"].strip()
        if not value:
            raise forms.ValidationError("Provider name is required.")
        return value

    def clean(self):
        cleaned = super().clean()
        method = cleaned.get("payout_method")
        phone = (cleaned.get("phone_number") or "").strip()
        account = (cleaned.get("account_number") or "").strip()
        if method == CashOutRequest.PayoutMethod.MOBILE_MONEY and not phone:
            self.add_error("phone_number", "Phone number is required for mobile money.")
        if method == CashOutRequest.PayoutMethod.BANK and not account:
            self.add_error("account_number", "Account number is required for bank payouts.")
        if method == CashOutRequest.PayoutMethod.MOBILE_MONEY and account:
            self.add_error("account_number", "Leave bank account number empty for mobile money.")
        if method == CashOutRequest.PayoutMethod.BANK and phone:
            self.add_error("phone_number", "Leave phone number empty for bank payouts.")
        cleaned["phone_number"] = phone
        cleaned["account_number"] = account
        return cleaned