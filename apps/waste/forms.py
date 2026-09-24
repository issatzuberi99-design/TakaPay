from django import forms

from .models import WasteCategory, WasteReport


class WasteReportForm(forms.ModelForm):
    class Meta:
        model = WasteReport
        fields = (
            "category",
            "description",
            "estimated_weight",
            "weight_unit",
            "estimated_piece_count",
            "latitude",
            "longitude",
            "location_accuracy",
            "photo",
        )
        widgets = {
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
            "location_accuracy": forms.HiddenInput(),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = WasteCategory.objects.filter(active=True)
        self.category_reward_units = {
            str(category.pk): category.reward_unit
            for category in self.fields["category"].queryset
        }
        self.fields["estimated_piece_count"].widget.attrs.update({"min": "1", "step": "1"})
        self.fields["weight_unit"].required = False

    def clean_category(self):
        category = self.cleaned_data["category"]
        if not category.active:
            raise forms.ValidationError("Please select an active waste category.")
        return category

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get("category")
        if category is None:
            return cleaned
        if category.reward_unit == WasteCategory.RewardUnit.PIECE:
            if cleaned.get("estimated_piece_count") is None:
                self.add_error("estimated_piece_count", "Enter a positive estimated number of pieces.")
            cleaned["estimated_weight"] = None
            cleaned["weight_unit"] = WasteReport.WeightUnit.KILOGRAMS
        else:
            if cleaned.get("estimated_weight") is None or cleaned["estimated_weight"] <= 0:
                self.add_error("estimated_weight", "Enter a positive estimated weight.")
            cleaned["estimated_piece_count"] = None
            cleaned["weight_unit"] = cleaned.get("weight_unit") or WasteReport.WeightUnit.KILOGRAMS
        return cleaned
