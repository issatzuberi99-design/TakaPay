from django.conf import settings
from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django.views.static import serve


def home(request):
    return render(request, "home.html")


def marketplace(request):
    return render(request, "placeholder.html", {"title": "Marketplace", "message": "Verified recyclable materials will appear here."})


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("home")


def service_worker(request):
    return serve(request, "service-worker.js", document_root=settings.BASE_DIR / "static")
