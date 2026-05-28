from django.urls import path
from . import views

urlpatterns = [
    path("", views.timesheet_list, name="timesheet_list"),
    path("create/", views.timesheet_create, name="timesheet_create"),
    path("today/", views.timesheet_today, name="timesheet_today"),
    path("template/download/", views.timesheet_template_download, name="timesheet_template_download"),
    path("upload/", views.timesheet_upload, name="timesheet_upload"),
    path("bulk-upload/", views.timesheet_bulk_zip_upload, name="timesheet_bulk_zip_upload"),
    path("bulk-upload/<int:job_pk>/", views.timesheet_bulk_zip_upload_status, name="timesheet_bulk_zip_upload_status"),
    path("bulk-upload/<int:job_pk>/api/", views.timesheet_bulk_zip_upload_status_api, name="timesheet_bulk_zip_upload_status_api"),
    path("approvals/", views.timesheet_approvals, name="timesheet_approvals"),
    path("<int:pk>/", views.timesheet_detail, name="timesheet_detail"),
    path("<int:pk>/edit/", views.timesheet_edit, name="timesheet_edit"),
    path("<int:pk>/download/", views.timesheet_download, name="timesheet_download"),
    path("<int:pk>/submit/", views.timesheet_submit, name="timesheet_submit"),
    path("artifacts/<int:artifact_pk>/download-ready/", views.timesheet_download_ready, name="timesheet_download_ready"),
    path("artifacts/<int:artifact_pk>/submitted/", views.timesheet_submitted_download, name="timesheet_submitted_download"),
    path("artifacts/<int:artifact_pk>/download/", views.timesheet_artifact_download, name="timesheet_artifact_download"),
    path("<int:pk>/receipts/upload/", views.timesheet_receipt_upload, name="timesheet_receipt_upload"),
    path("receipts/<int:receipt_pk>/download/", views.timesheet_receipt_download, name="timesheet_receipt_download"),
    path("receipts/<int:receipt_pk>/delete/", views.timesheet_receipt_delete, name="timesheet_receipt_delete"),
    path("<int:pk>/reopen/", views.timesheet_reopen, name="timesheet_reopen"),
    path("<int:pk>/approve/", views.timesheet_approve, name="timesheet_approve"),
    path("<int:pk>/reject/", views.timesheet_reject, name="timesheet_reject"),
    path("<int:pk>/mark-invoiced/", views.timesheet_mark_invoiced, name="timesheet_mark_invoiced"),
    path("<int:pk>/delete/", views.timesheet_delete, name="timesheet_delete"),
]
