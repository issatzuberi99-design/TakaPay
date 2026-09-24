from django import forms
from django.forms import modelformset_factory
from django.utils import timezone

from apps.marketplace.models import MarketplaceMaterial
from apps.rewards.models import Reward
from apps.waste.models import WasteCategory
from apps.economics.models import CollectorBonus, EconomicPolicy, EconomicSetting, MaterialRate


class WasteCategoryRateForm(forms.ModelForm):
    class Meta:
        model = WasteCategory
        fields = ("reward_unit", "token_rate", "active")
        labels = {"token_rate": "Token Rate"}
        widgets = {"token_rate": forms.NumberInput(attrs={"min": "0", "step": "0.01"})}


TokenRateFormSet = modelformset_factory(
    WasteCategory,
    form=WasteCategoryRateForm,
    extra=0,
)


class MarketplacePreparationForm(forms.ModelForm):
    class Meta:
        model = MarketplaceMaterial
        fields = (
            "name", "description", "category", "image", "available_quantity", "unit",
            "price_per_unit", "preparation_status",
        )
        widgets = {
            "available_quantity": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "price_per_unit": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("preparation_status") == MarketplaceMaterial.PreparationStatus.PUBLISHED:
            if not (cleaned.get("name") or "").strip():
                self.add_error("name", "Add a marketplace material name before publishing.")
            if not (cleaned.get("description") or "").strip():
                self.add_error("description", "Add a public description before publishing.")
            if cleaned.get("category") is None:
                self.add_error("category", "Select a material category before publishing.")
            if cleaned.get("available_quantity") is None or cleaned["available_quantity"] <= 0:
                self.add_error("available_quantity", "Published material must have quantity greater than zero.")
        return cleaned


class RewardOperationsForm(forms.ModelForm):
    class Meta:
        model = Reward
        fields = ("name", "description", "image", "token_cost", "inventory", "active")
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class EconomicPolicyForm(forms.ModelForm):
    class Meta:
        model = EconomicPolicy
        fields = ("name", "category", "customer_percent", "collector_percent", "operations_percent", "active", "effective_from")
        widgets = {"effective_from": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def clean(self):
        cleaned = super().clean()
        total = sum((cleaned.get(field) or 0 for field in ("customer_percent", "collector_percent", "operations_percent")))
        if total != 100:
            raise forms.ValidationError("The three economic percentages must total exactly 100%.")
        return cleaned


class MaterialRateForm(forms.ModelForm):
    class Meta:
        model = MaterialRate
        fields = ("category", "rate_per_unit", "currency", "active", "effective_from")
        widgets = {"effective_from": forms.DateTimeInput(attrs={"type": "datetime-local"})}


class CollectorBonusForm(forms.ModelForm):
    class Meta:
        model = CollectorBonus
        fields = ("name", "amount", "active", "effective_from", "effective_until", "eligibility_description")
        widgets = {
            "effective_from": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "effective_until": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "eligibility_description": forms.Textarea(attrs={"rows": 3}),
        }


class EconomicSettingForm(forms.ModelForm):
    class Meta:
        model = EconomicSetting
        fields = ("customer_cashout_min_tokens", "collector_payout_min_tzs")
