from django.urls import path

from . import views

urlpatterns = [
    path("", views.cashout_create, name="cashout_create"),
    path("history/", views.cashout_history, name="cashout_history"),
]