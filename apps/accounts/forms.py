import re

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.db.models import Q

from .models import CollectorProfile, User


def normalize_phone(raw):
    """Return a phone number as +<country><number>, or None if it is not valid.

    Accepts 0712345678, 255712345678, +255 712 345 678, 00255712345678.
    A leading 0 is treated as Tanzania. Other countries must start with + or 00.
    """
    value = re.sub(r"[\s\-().]", "", (raw or "").strip())
    if value.startswith("00"):
        value = "+" + value[2:]
    if value.startswith("0"):
        value = "+255" + value[1:]
    elif value.startswith("255"):
        value = "+" + value
    if not re.fullmatch(r"\+\d{9,15}", value):
        return None
    if value.startswith("+255") and len(value) != 13:
        return None
    return value


class BaseRegistrationForm(UserCreationForm):
    phone_number = forms.CharField(
        label="Phone number",
        max_length=20,
        help_text="Used to coordinate pickups. Example: 0712 345 678.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "phone_number", "email", "username")

    field_order = ["first_name", "last_name", "phone_number", "email", "username", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["email"].help_text = "Optional. You can also use it to log in."
        self.fields["username"].help_text = "Letters, numbers and @ . + - _ only."
        self.fields["password1"].help_text = "Use at least 8 characters. Avoid common or all-number passwords."
        self.fields["password2"].label = "Confirm password"
        self.fields["password2"].help_text = ""

        autofill = {
            "first_name": {"autocomplete": "given-name"},
            "last_name": {"autocomplete": "family-name"},
            "phone_number": {"autocomplete": "tel", "inputmode": "tel", "placeholder": "0712 345 678"},
            "email": {"autocomplete": "email", "placeholder": "you@example.com"},
            "username": {"autocomplete": "username", "autocapitalize": "none", "spellcheck": "false"},
            "password1": {"autocomplete": "new-password"},
            "password2": {"autocomplete": "new-password"},
        }
        for name, attrs in autofill.items():
            self.fields[name].widget.attrs.update(attrs)

    def clean_phone_number(self):
        phone = normalize_phone(self.cleaned_data.get("phone_number"))
        if phone is None:
            raise forms.ValidationError(
                "Enter a valid phone number, for example 0712 345 678 or +255 712 345 678."
            )
        if User.objects.filter(phone_number=phone).exists():
            raise forms.ValidationError("An account with this phone number already exists. Try logging in.")
        return phone

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists. Try logging in.")
        return email


class CustomerRegistrationForm(BaseRegistrationForm):
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.CUSTOMER
        if commit:
            user.save()
        return user


class CollectorRegistrationForm(BaseRegistrationForm):
    identification_reference = forms.CharField(
        label="ID number",
        max_length=100,
        help_text="NIDA, Zanzibar ID or passport number. Used only to verify your application.",
    )
    address = forms.CharField(
        label="Where you collect from",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Shehia or neighbourhood, plus a nearby landmark"}),
        help_text="The area you work in and where we can find you.",
    )

    field_order = [
        "first_name", "last_name", "phone_number", "email", "username",
        "identification_reference", "address", "password1", "password2",
    ]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.COLLECTOR
        user.collector_verification_status = User.CollectorVerificationStatus.PENDING
        if commit:
            with transaction.atomic():
                user.save()
                CollectorProfile.objects.create(
                    user=user,
                    identification_reference=self.cleaned_data["identification_reference"],
                    address=self.cleaned_data["address"],
                )
        return user


class TakaPayAuthenticationForm(forms.Form):
    identifier = forms.CharField(
        label="Username, email or phone",
        widget=forms.TextInput(
            attrs={"autocomplete": "username", "autocapitalize": "none", "spellcheck": "false", "autofocus": True}
        ),
    )
    password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def _resolve_username(self, identifier):
        identifier = identifier.strip()
        lookup = Q(email__iexact=identifier)
        phone = normalize_phone(identifier)
        if phone:
            lookup |= Q(phone_number=phone)
        user = User.objects.filter(lookup).first()
        return user.username if user else identifier

    def clean(self):
        cleaned_data = super().clean()
        identifier = cleaned_data.get("identifier")
        password = cleaned_data.get("password")
        if identifier and password:
            username = self._resolve_username(identifier)
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                raise forms.ValidationError(
                    "We could not sign you in. Check your username, email or phone, and your password."
                )
            if not self.user_cache.is_active:
                raise forms.ValidationError("This account is inactive.")
        return cleaned_data

    def get_user(self):
        return self.user_cache