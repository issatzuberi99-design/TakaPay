from django import forms

from .models import BuyerRequest


class BuyerRequestForm(forms.ModelForm):
    class Meta:
        model = BuyerRequest
        fields = ("buyer_name", "company_name", "phone_number", "email", "location", "requested_quantity", "message")
        widgets = {"requested_quantity": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"})}

    def __init__(self, material, *args, **kwargs):
        self.material = material
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        for field in ("buyer_name", "phone_number", "location"):
            value = (cleaned.get(field) or "").strip()
            if not value:
                self.add_error(field, "This field is required.")
            cleaned[field] = value
        email = (cleaned.get("email") or "").strip()
        if not email:
            self.add_error("email", "This field is required.")
        cleaned["email"] = email
        cleaned["company_name"] = (cleaned.get("company_name") or "").strip()
        cleaned["message"] = (cleaned.get("message") or "").strip()
        quantity = cleaned.get("requested_quantity")
        if quantity is not None and quantity > self.material.available_quantity:
            self.add_error("requested_quantity", "Requested quantity exceeds current availability.")
        return cleaned

    def save(self, commit=True):
        request = super().save(commit=False)
        request.material = self.material
        request.material_name = self.material.name
        request.unit = self.material.unit
        request.price_per_unit = self.material.price_per_unit
        if commit:
            request.save()
        return request
