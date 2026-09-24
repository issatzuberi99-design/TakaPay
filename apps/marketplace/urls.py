from django.urls import path

from . import views

urlpatterns = [
    path("", views.marketplace_list, name="marketplace"),
    path("<int:material_id>/", views.material_detail, name="marketplace_material_detail"),
    path("<int:material_id>/request/", views.buyer_request_create, name="buyer_request_create"),
    path("request/<int:request_id>/confirmation/", views.buyer_request_confirmation, name="buyer_request_confirmation"),
]
