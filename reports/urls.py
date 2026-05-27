
from django.urls import path
from . import views

urlpatterns = [
    path("", views.reports_dashboard, name="reports_dashboard"),
    path("billability/", views.billability_report, name="billability_report"),
    path("my-billability/", views.my_billability_report, name="my_billability_report"),
    path("project-hours/", views.project_hours_report, name="project_hours_report"),
]
