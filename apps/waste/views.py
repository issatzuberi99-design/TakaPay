from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.decorators import role_required
from apps.accounts.models import User

from .forms import WasteReportForm
from .models import WasteReport


@role_required(User.Role.CUSTOMER)
def report_create(request):
    form = WasteReportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        report = form.save(commit=False)
        report.customer = request.user
        report.status = WasteReport.Status.SUBMITTED
        report.save()
        messages.success(request, "Your waste report was submitted successfully.")
        return redirect("waste_report_detail", report_id=report.id)
    return render(request, "waste/report_form.html", {"form": form})


@role_required(User.Role.CUSTOMER)
def report_list(request):
    reports = WasteReport.objects.filter(customer=request.user).select_related("category")
    return render(request, "waste/report_list.html", {"reports": reports})


@role_required(User.Role.CUSTOMER)
def report_detail(request, report_id):
    report = get_object_or_404(
        WasteReport.objects.select_related("category"),
        id=report_id,
        customer=request.user,
    )
    return render(request, "waste/report_detail.html", {"report": report})