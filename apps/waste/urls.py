from django.urls import path

from . import views

urlpatterns = [
    path("report/", views.report_create, name="waste_report_create"),
    path("reports/", views.report_list, name="waste_report_list"),
    path("reports/<int:report_id>/", views.report_detail, name="waste_report_detail"),
]