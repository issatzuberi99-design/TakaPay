from django import forms

from apps.waste.models import WasteReport

from .models import CollectionRequest


class CollectionCompletionForm(forms.ModelForm):
    class Meta:
        model = CollectionRequest
        fields = ("actual_weight", "weight_unit", "proof_photo", "notes")

    def clean_actual_weight(self):
        actual_weight = self.cleaned_data.get("actual_weight")
        if actual_weight is None or actual_weight <= 0:
            raise forms.ValidationError("Actual collected weight must be greater than zero.")
        return actual_weight

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("proof_photo"):
            raise forms.ValidationError("A proof photo is required to complete the collection.")
        return cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["weight_unit"].choices = WasteReport.WeightUnit.choices
        self.fields["proof_photo"].required = True
        self.fields["notes"].widget.attrs.update({"rows": 4})
