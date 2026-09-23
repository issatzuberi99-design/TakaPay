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

    def clean_category(self):
        category = self.cleaned_data["category"]
        if not category.active:
            raise forms.ValidationError("Please select an active waste category.")
        return category