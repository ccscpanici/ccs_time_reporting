from django.urls import path

from absence import views

urlpatterns = [
    path("", views.absence_list, name="absence_list"),
    path("new/", views.absence_create, name="absence_create"),
    path("<int:pk>/", views.absence_detail, name="absence_detail"),
    path("<int:pk>/edit/", views.absence_edit, name="absence_edit"),
    path("<int:pk>/submit/", views.absence_submit, name="absence_submit"),
    path("<int:pk>/approve/", views.absence_approve, name="absence_approve"),
    path("<int:pk>/deny/", views.absence_deny, name="absence_deny"),
    path("<int:pk>/exception/approve/", views.exception_approve, name="absence_exception_approve"),
    path("<int:pk>/exception/deny/", views.exception_deny, name="absence_exception_deny"),
    path("approvals/", views.absence_approvals, name="absence_approvals"),
    path("pto/", views.pto_balance_list, name="pto_balance_list"),
    path("pto/<int:user_id>/edit/", views.pto_balance_edit, name="pto_balance_edit"),
    path("pto/imports/", views.pto_import_list, name="pto_import_list"),
    path("pto/import/", views.pto_import_upload, name="pto_import_upload"),
    path("pto/import/<int:pk>/", views.pto_import_preview, name="pto_import_preview"),
    path("pto/import/<int:pk>/apply/", views.pto_import_apply, name="pto_import_apply"),
    path("pto/import/row/<int:row_id>/match/", views.pto_import_match, name="pto_import_match"),
    path("artifacts/<int:artifact_id>/download/", views.absence_artifact_download, name="absence_artifact_download"),
]
