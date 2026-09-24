from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from .analytics import dashboard_context
from .decorators import approved_collector_required
from .forms import (
    CollectorRegistrationForm,
    CustomerRegistrationForm,
    TakaPayAuthenticationForm,
)
from .models import User


def register(request):
    form = CustomerRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Account created successfully.")
        return redirect("login")
    return render(request, "accounts/register.html", {"form": form})


def collector_register(request):
    form = CollectorRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your collector application has been submitted and is awaiting verification.")
        return redirect("login")
    return render(request, "accounts/collector_register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = TakaPayAuthenticationForm(request, request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        messages.success(request, "Welcome to TakaPay.")
        return redirect("dashboard")
    return render(request, "accounts/login.html", {"form": form})


@login_required
def dashboard(request):
    if request.user.role == User.Role.COLLECTOR:
        profile = getattr(request.user, "collector_profile", None)
        if profile is None or profile.verification_status != profile.VerificationStatus.APPROVED:
            return render(request, "accounts/pending_verification.html")
        return render(request, "accounts/collector_dashboard.html")
    if request.user.role == User.Role.ADMIN:
        return redirect("admin_analytics_dashboard")
    return render(request, "accounts/customer_dashboard.html")


@approved_collector_required
def collector_jobs(request):
    return render(request, "placeholder.html", {"title": "Collection jobs", "message": "Collection jobs will be added in a later task."})


@login_required
def admin_analytics_dashboard(request):
    can_view = request.user.is_active and (
        request.user.is_staff
        or request.user.is_superuser
        or request.user.role == User.Role.ADMIN
    )
    if not can_view:
        raise PermissionDenied
    return render(request, "accounts/admin_dashboard.html", dashboard_context(request))


@login_required
def admin_dashboard(request):
    if not (
        request.user.is_staff
        or request.user.is_superuser
        or request.user.role == User.Role.ADMIN
    ):
        raise PermissionDenied
    return redirect("admin_analytics_dashboard")
