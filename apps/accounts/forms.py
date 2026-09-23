from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm

from .models import CollectorProfile, User


class CustomerRegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "username", "email", "phone_number")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.CUSTOMER
        if commit:
            user.save()
        return user


class CollectorRegistrationForm(UserCreationForm):
    identification_reference = forms.CharField(max_length=100)
    address = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))

    class Meta:
        model = User
        fields = ("first_name", "last_name", "username", "email", "phone_number")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.COLLECTOR
        user.collector_verification_status = User.CollectorVerificationStatus.PENDING
        if commit:
            user.save()
            CollectorProfile.objects.create(
                user=user,
                identification_reference=self.cleaned_data["identification_reference"],
                address=self.cleaned_data["address"],
            )
        return user


class TakaPayAuthenticationForm(forms.Form):
    identifier = forms.CharField(label="Username or email")
    password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        identifier = cleaned_data.get("identifier")
        password = cleaned_data.get("password")
        if identifier and password:
            username = identifier
            user = User.objects.filter(email__iexact=identifier).first()
            if user:
                username = user.username
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                raise forms.ValidationError("Please enter a valid username/email and password.")
            if not self.user_cache.is_active:
                raise forms.ValidationError("This account is inactive.")
        return cleaned_data

    def get_user(self):
        return self.user_cache