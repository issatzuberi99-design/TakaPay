from django import forms
from django.forms import modelformset_factory

from apps.marketplace.models import MarketplaceMaterial
from apps.rewards.models import Reward
from apps.waste.models import WasteCategory


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
