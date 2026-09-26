from django import forms

from apps.waste.models import WasteCategory, WasteReport

from .models import CollectionRequest


class CollectionCompletionForm(forms.ModelForm):
    class Meta:
        model = CollectionRequest
        fields = ("actual_weight", "actual_piece_count", "weight_unit", "proof_photo", "notes")

    def __init__(self, *args, category, **kwargs):
        self.category = category
        super().__init__(*args, **kwargs)
        if category.reward_unit == WasteCategory.RewardUnit.PIECE:
            self.fields.pop("actual_weight")
            self.fields.pop("weight_unit")
            self.fields["actual_piece_count"].label = "Verified Quantity (pieces)"
            self.fields["actual_piece_count"].help_text = "Enter the collector-verified number of individual pieces."
            self.fields["actual_piece_count"].widget.attrs.update({"min": "1", "step": "1", "required": True})
        else:
            self.fields.pop("actual_piece_count")
            self.fields["actual_weight"].label = "Verified Weight"
            self.fields["weight_unit"].choices = WasteReport.WeightUnit.choices
            self.fields["actual_weight"].widget.attrs.update({"min": "0.01", "step": "0.01", "required": True})
        self.fields["proof_photo"].required = True
        self.fields["proof_photo"].widget.attrs["required"] = True
        self.fields["notes"].widget.attrs.update({"rows": 4})

    def clean_actual_weight(self):
        actual_weight = self.cleaned_data.get("actual_weight")
        if self.category.reward_unit == WasteCategory.RewardUnit.KILOGRAM and (actual_weight is None or actual_weight <= 0):
            raise forms.ValidationError("Actual collected weight must be greater than zero.")
        return actual_weight

    def clean_actual_piece_count(self):
        piece_count = self.cleaned_data.get("actual_piece_count")
        if self.category.reward_unit == WasteCategory.RewardUnit.PIECE and (piece_count is None or piece_count <= 0):
            raise forms.ValidationError("Verified piece quantity must be greater than zero.")
        return piece_count

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("proof_photo"):
            raise forms.ValidationError("A proof photo is required to complete the collection.")
        return cleaned_data
