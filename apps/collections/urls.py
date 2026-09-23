from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.collections_dashboard, name="collections_dashboard"),
    path("<int:collection_id>/", views.collection_detail, name="collection_detail"),
    path("<int:collection_id>/accept/", views.accept_collection, name="collection_accept"),
    path("<int:collection_id>/complete/", views.complete_collection, name="collection_complete"),
]
