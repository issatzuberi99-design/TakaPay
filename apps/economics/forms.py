from django import forms

from .models import CollectorPayout


class CollectorPayoutForm(forms.ModelForm):
    class Meta:
        model = CollectorPayout
        fields = ("amount", "payout_method", "provider_name", "destination")
        widgets = {"amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"})}

    def clean_destination(self):
        value = self.cleaned_data["destination"].strip()
        if not value:
            raise forms.ValidationError("A payout destination is required.")
        return value
