from django.urls import path

from . import views

urlpatterns = [
    path("payout/", views.collector_payout_create, name="collector_payout_create"),
]
