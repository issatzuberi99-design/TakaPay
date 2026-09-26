from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from .forms import BuyerRequestForm
from .models import BuyerRequest, MarketplaceMaterial


def available_materials():
    return MarketplaceMaterial.objects.filter(
        active=True,
        preparation_status=MarketplaceMaterial.PreparationStatus.PUBLISHED,
        available_quantity__gt=0,
    ).select_related("category")


def marketplace_list(request):
    page_obj = Paginator(available_materials(), 12).get_page(request.GET.get("page"))
    return render(request, "marketplace/material_list.html", {"materials": page_obj.object_list, "page_obj": page_obj})


def material_detail(request, material_id):
    material = get_object_or_404(available_materials(), pk=material_id)
    return render(request, "marketplace/material_detail.html", {"material": material, "form": BuyerRequestForm(material)})


def buyer_request_create(request, material_id):
    material = get_object_or_404(available_materials(), pk=material_id)
    if request.method == "POST":
        form = BuyerRequestForm(material, request.POST)
        if form.is_valid():
            buyer_request = form.save()
            request.session["marketplace_confirmation_id"] = buyer_request.pk
            return redirect("buyer_request_confirmation", request_id=buyer_request.pk)
    else:
        form = BuyerRequestForm(material)
    return render(request, "marketplace/request_form.html", {"material": material, "form": form})


def buyer_request_confirmation(request, request_id):
    if request.session.get("marketplace_confirmation_id") != request_id:
        raise Http404
    buyer_request = get_object_or_404(BuyerRequest, pk=request_id)
    return render(request, "marketplace/request_confirmation.html", {"buyer_request": buyer_request})
