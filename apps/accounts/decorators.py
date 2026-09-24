from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .models import User


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(request, *args, **kwargs):
            if request.user.role not in roles:
                messages.error(request, "You do not have permission to access this page.")
                return redirect("dashboard")
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


def approved_collector_required(view):
    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        profile = getattr(request.user, "collector_profile", None)
        is_approved = (
            request.user.role == User.Role.COLLECTOR
            and profile is not None
            and profile.verification_status == profile.VerificationStatus.APPROVED
        )
        if not is_approved:
            messages.warning(request, "Your collector account is not yet approved for collection jobs.")
            return redirect("dashboard")
        return view(request, *args, **kwargs)

    return wrapped

def platform_admin_required(view):
    """Allow active TakaPay admins and Django staff to use operational screens."""
    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        user = request.user
        if not user.is_active or not (user.is_staff or user.is_superuser or user.role == User.Role.ADMIN):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped
