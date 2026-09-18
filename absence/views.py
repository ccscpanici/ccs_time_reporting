from __future__ import annotations

from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from absence.forms import AbsenceRequestForm, DecisionForm, PTOAccountForm, PTOImportUploadForm
from absence.models import AbsenceArtifact, AbsenceRequest, PTOAccount, PTOImport, PTOImportRow
from absence.permissions import (
    can_decide_exception,
    can_import_pto,
    can_manage_pto_account,
    can_supervisor_decide,
    can_view_absence_request,
    employees_manageable_by,
)
from absence.services.pdf import ensure_final_pdf
from absence.services.pto_balances import vacation_summary
from absence.services.pto_import import (
    account_snapshot,
    apply_pto_import,
    build_import_preview,
    record_manual_account_change,
)
from absence.services.request_days import parse_daily_hours, request_day_minutes, save_request_days
from absence.services.time_values import is_full_employment_week_range
from timesheets.permissions import is_management_staff, is_project_manager

User = get_user_model()


def _posted_daily_hours(data):
    values = {}
    for key, value in data.items():
        if key.startswith("day_hours_") and value not in (None, ""):
            values[key.removeprefix("day_hours_")] = value
    return values


def _archive_final_request(request_obj, actor, request=None):
    try:
        return ensure_final_pdf(request_obj, generated_by=actor)
    except Exception as exc:
        if request is not None:
            messages.error(
                request,
                f"The request was finalized, but the PDF could not be archived: {exc}",
            )
        return None


@login_required
def absence_list(request):
    requests = AbsenceRequest.objects.filter(employee=request.user).select_related("manager")
    pto_account = PTOAccount.objects.filter(employee=request.user).first()
    pto_summary = vacation_summary(pto_account) if pto_account else None
    return render(
        request,
        "absence/list.html",
        {
            "absence_requests": requests,
            "pto_account": pto_account,
            "pto_summary": pto_summary,
        },
    )


@login_required
def absence_create(request):
    account = PTOAccount.objects.filter(employee=request.user).first()
    if request.method == "POST":
        form = AbsenceRequestForm(request.POST, employee=request.user)
        if form.is_valid():
            absence = form.save(commit=False)
            absence.employee = request.user
            absence.status = AbsenceRequest.Status.DRAFT
            daily_values = parse_daily_hours(request.POST, absence.start_date, absence.end_date)
            absence.requested_minutes = sum(minutes for _, minutes in daily_values)
            current_projected = vacation_summary(account).projected_vacation_balance_minutes if account else 0
            absence.negative_balance_exception_required = bool(
                absence.absence_type == AbsenceRequest.AbsenceType.VACATION
                and current_projected - absence.requested_minutes < AbsenceRequest.MIN_VACATION_BALANCE_MINUTES
            )
            absence.save()
            save_request_days(absence, daily_values)
            messages.success(request, "Absence request created as a draft. Review it and submit when ready.")
            return redirect("absence_detail", pk=absence.pk)
    else:
        form = AbsenceRequestForm(employee=request.user)
    return render(request, "absence/request_form.html", {
        "form": form,
        "pto_account": account,
        "pto_summary": vacation_summary(account) if account else None,
        "daily_hours": _posted_daily_hours(request.POST) if request.method == "POST" else {},
    })


@login_required
def absence_edit(request, pk):
    absence = get_object_or_404(AbsenceRequest, pk=pk, employee=request.user, status=AbsenceRequest.Status.DRAFT)
    account = PTOAccount.objects.filter(employee=request.user).first()
    if request.method == "POST":
        form = AbsenceRequestForm(request.POST, instance=absence, employee=request.user)
        if form.is_valid():
            absence = form.save(commit=False)
            daily_values = parse_daily_hours(request.POST, absence.start_date, absence.end_date)
            absence.requested_minutes = sum(minutes for _, minutes in daily_values)
            current_projected = vacation_summary(account).projected_vacation_balance_minutes if account else 0
            absence.negative_balance_exception_required = bool(
                absence.absence_type == AbsenceRequest.AbsenceType.VACATION
                and current_projected - absence.requested_minutes < AbsenceRequest.MIN_VACATION_BALANCE_MINUTES
            )
            absence.save()
            save_request_days(absence, daily_values)
            messages.success(request, "Draft updated.")
            return redirect("absence_detail", pk=absence.pk)
    else:
        form = AbsenceRequestForm(instance=absence, employee=request.user)
    return render(
        request,
        "absence/request_form.html",
        {
            "form": form,
            "pto_account": account,
            "pto_summary": vacation_summary(account) if account else None,
            "absence": absence,
            "editing": True,
            "daily_hours": (
                _posted_daily_hours(request.POST)
                if request.method == "POST"
                else {day.isoformat(): minutes / 60 for day, minutes in request_day_minutes(absence)}
            ),
        },
    )


@login_required
def absence_detail(request, pk):
    absence = get_object_or_404(
        AbsenceRequest.objects.select_related(
            "employee", "manager", "submitted_by", "supervisor_approved_by", "supervisor_denied_by",
            "exception_approved_by", "exception_denied_by"
        ),
        pk=pk,
    )
    if not can_view_absence_request(request.user, absence):
        raise Http404
    pto_account = PTOAccount.objects.filter(employee=absence.employee).first()
    current_pto_summary = vacation_summary(pto_account) if pto_account else None
    return render(
        request,
        "absence/detail.html",
        {
            "absence": absence,
            "pto_account": pto_account,
            "current_pto_summary": current_pto_summary,
            "can_supervisor_decide": can_supervisor_decide(request.user, absence),
            "can_decide_exception": can_decide_exception(request.user, absence),
            "decision_form": DecisionForm(),
            "request_days": list(absence.days.all()),
        },
    )


@login_required
@transaction.atomic
def absence_submit(request, pk):
    if request.method != "POST":
        return HttpResponseForbidden("POST required")
    absence = get_object_or_404(AbsenceRequest, pk=pk, employee=request.user)
    if absence.status != AbsenceRequest.Status.DRAFT:
        messages.error(request, "Only draft absence requests can be submitted.")
        return redirect("absence_detail", pk=absence.pk)

    profile = getattr(request.user, "employee_profile", None)
    account = PTOAccount.objects.filter(employee=request.user).first()
    absence.manager = profile.supervisor if profile else None
    if absence.manager is None and (is_project_manager(request.user) or is_management_staff(request.user)):
        absence.manager = request.user
    absence.submitted_by = request.user
    absence.submitted_at = timezone.now()
    absence.status = AbsenceRequest.Status.SUBMITTED
    absence.requested_minutes = sum(minutes for _, minutes in request_day_minutes(absence))
    absence.late_notice = bool(
        absence.absence_type != AbsenceRequest.AbsenceType.SICK
        and (absence.start_date - timezone.localdate()).days < 14
    )

    if account:
        summary = vacation_summary(account)
        absence.vacation_weeks_per_year_snapshot = account.vacation_weeks_per_year
        absence.vacation_balance_snapshot_minutes = summary.vacation_balance_minutes
        absence.sick_balance_snapshot_minutes = account.sick_available_minutes
        absence.balance_as_of_snapshot = account.balance_as_of
    else:
        summary = None
        absence.vacation_weeks_per_year_snapshot = 0
        absence.vacation_balance_snapshot_minutes = 0
        absence.sick_balance_snapshot_minutes = 0
        absence.balance_as_of_snapshot = None

    if absence.absence_type == AbsenceRequest.AbsenceType.VACATION:
        current_after_approved = summary.projected_vacation_balance_minutes if summary else 0
        absence.projected_vacation_balance_minutes = (
            current_after_approved - absence.requested_minutes
        )
        absence.negative_balance_exception_required = (
            absence.projected_vacation_balance_minutes < AbsenceRequest.MIN_VACATION_BALANCE_MINUTES
        )
        if absence.negative_balance_exception_required and (
            not absence.negative_balance_acknowledged
            or not is_full_employment_week_range(absence.unpaid_start_date, absence.unpaid_end_date)
        ):
            messages.error(
                request,
                "The current PTO balance now requires a negative-balance exception. Edit the draft with the required acknowledgment and full unpaid employment week(s).",
            )
            return redirect("absence_detail", pk=absence.pk)
    else:
        absence.projected_vacation_balance_minutes = None
        absence.negative_balance_exception_required = False

    absence.save()
    if absence.late_notice:
        messages.warning(request, "This request is inside the normal two-week advance notice window and has been flagged for the approver.")
    messages.success(request, "Absence request submitted for approval.")
    return redirect("absence_detail", pk=absence.pk)


@login_required
def absence_approvals(request):
    if not (is_project_manager(request.user) or is_management_staff(request.user)):
        return HttpResponseForbidden("Supervisor access required.")

    qs = AbsenceRequest.objects.select_related("employee", "manager")
    if is_management_staff(request.user):
        requests = qs.filter(status__in=[AbsenceRequest.Status.SUBMITTED, AbsenceRequest.Status.PENDING_EXCEPTION])
    else:
        requests = qs.filter(status=AbsenceRequest.Status.SUBMITTED, manager=request.user)
    return render(request, "absence/approvals.html", {"absence_requests": requests})


@login_required
@transaction.atomic
def absence_approve(request, pk):
    if request.method != "POST":
        return HttpResponseForbidden("POST required")
    absence = get_object_or_404(AbsenceRequest, pk=pk)
    if not can_supervisor_decide(request.user, absence):
        raise Http404
    form = DecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Unable to record the approval.")
        return redirect("absence_detail", pk=absence.pk)

    absence.supervisor_approved_by = request.user
    absence.supervisor_approved_at = timezone.now()
    absence.supervisor_notes = form.cleaned_data.get("notes", "")
    if absence.negative_balance_exception_required:
        absence.status = AbsenceRequest.Status.PENDING_EXCEPTION
        messages.success(request, "Supervisor approval recorded. This request now requires negative-balance exception approval.")
    else:
        absence.status = AbsenceRequest.Status.APPROVED
        absence.finalized_at = timezone.now()
        messages.success(request, "Absence request approved.")
    absence.save()
    if absence.is_final:
        _archive_final_request(absence, request.user, request=request)
    return redirect("absence_detail", pk=absence.pk)


@login_required
@transaction.atomic
def absence_deny(request, pk):
    if request.method != "POST":
        return HttpResponseForbidden("POST required")
    absence = get_object_or_404(AbsenceRequest, pk=pk)
    if not can_supervisor_decide(request.user, absence):
        raise Http404
    form = DecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Unable to record the denial.")
        return redirect("absence_detail", pk=absence.pk)

    absence.supervisor_denied_by = request.user
    absence.supervisor_denied_at = timezone.now()
    absence.supervisor_notes = form.cleaned_data.get("notes", "")
    absence.status = AbsenceRequest.Status.DENIED
    absence.finalized_at = timezone.now()
    absence.save()
    _archive_final_request(absence, request.user, request=request)
    messages.success(request, "Absence request denied.")
    return redirect("absence_detail", pk=absence.pk)


@login_required
@transaction.atomic
def exception_approve(request, pk):
    if request.method != "POST":
        return HttpResponseForbidden("POST required")
    absence = get_object_or_404(AbsenceRequest, pk=pk)
    if not can_decide_exception(request.user, absence):
        raise Http404
    form = DecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Unable to record the exception approval.")
        return redirect("absence_detail", pk=absence.pk)
    absence.exception_approved_by = request.user
    absence.exception_approved_at = timezone.now()
    absence.exception_notes = form.cleaned_data.get("notes", "")
    absence.status = AbsenceRequest.Status.APPROVED
    absence.finalized_at = timezone.now()
    absence.save()
    _archive_final_request(absence, request.user, request=request)
    messages.success(request, "Negative-balance exception approved. The absence request is finalized.")
    return redirect("absence_detail", pk=absence.pk)


@login_required
@transaction.atomic
def exception_deny(request, pk):
    if request.method != "POST":
        return HttpResponseForbidden("POST required")
    absence = get_object_or_404(AbsenceRequest, pk=pk)
    if not can_decide_exception(request.user, absence):
        raise Http404
    form = DecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Unable to record the exception denial.")
        return redirect("absence_detail", pk=absence.pk)
    absence.exception_denied_by = request.user
    absence.exception_denied_at = timezone.now()
    absence.exception_notes = form.cleaned_data.get("notes", "")
    absence.status = AbsenceRequest.Status.DENIED
    absence.finalized_at = timezone.now()
    absence.save()
    _archive_final_request(absence, request.user, request=request)
    messages.success(request, "Negative-balance exception denied. The absence request is finalized as denied.")
    return redirect("absence_detail", pk=absence.pk)


@login_required
def pto_balance_list(request):
    employees = employees_manageable_by(request.user)
    if not (is_project_manager(request.user) or is_management_staff(request.user)):
        return HttpResponseForbidden("Supervisor access required.")
    accounts = {
        account.employee_id: account
        for account in PTOAccount.objects.filter(employee__in=employees).select_related("employee", "updated_by")
    }
    rows = []
    for employee in employees:
        account = accounts.get(employee.id)
        rows.append({
            "employee": employee,
            "account": account,
            "summary": vacation_summary(account) if account else None,
        })
    return render(request, "absence/pto_balance_list.html", {"rows": rows})


@login_required
@transaction.atomic
def pto_balance_edit(request, user_id):
    employee = get_object_or_404(User, pk=user_id, is_active=True)
    if not can_manage_pto_account(request.user, employee):
        raise Http404
    account, _ = PTOAccount.objects.get_or_create(employee=employee)
    old = account_snapshot(account)
    if request.method == "POST":
        form = PTOAccountForm(request.POST, account=account)
        if form.is_valid():
            form.save(updated_by=request.user)
            record_manual_account_change(account, old, request.user, note=form.cleaned_data.get("note", ""))
            messages.success(request, f"PTO balances updated for {employee.get_full_name() or employee.username}.")
            return redirect("pto_balance_list")
    else:
        form = PTOAccountForm(account=account)
    return render(request, "absence/pto_balance_edit.html", {"form": form, "employee": employee, "account": account})


@login_required
def pto_import_list(request):
    if not can_import_pto(request.user):
        return HttpResponseForbidden("Management Staff access required.")
    imports = PTOImport.objects.select_related("uploaded_by", "applied_by")
    return render(request, "absence/pto_import_list.html", {"imports": imports})


@login_required
def pto_import_upload(request):
    if not can_import_pto(request.user):
        return HttpResponseForbidden("Management Staff access required.")
    if request.method == "POST":
        form = PTOImportUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.cleaned_data["source_file"]
            pto_import = PTOImport.objects.create(
                source_file=upload,
                source_name=upload.name,
                uploaded_by=request.user,
            )
            try:
                build_import_preview(pto_import)
            except Exception as exc:
                messages.error(request, f"Unable to read PTO report: {exc}")
            else:
                messages.success(request, "PTO report parsed. Review the matches and changes before applying it.")
            return redirect("pto_import_preview", pk=pto_import.pk)
    else:
        form = PTOImportUploadForm()
    return render(request, "absence/pto_import_upload.html", {"form": form})


@login_required
def pto_import_preview(request, pk):
    if not can_import_pto(request.user):
        return HttpResponseForbidden("Management Staff access required.")

    pto_import = get_object_or_404(
        PTOImport.objects.select_related("uploaded_by", "applied_by"),
        pk=pk,
    )

    rows = list(pto_import.rows.select_related("employee"))

    accounts = {
        account.employee_id: account
        for account in PTOAccount.objects.filter(
            employee_id__in=[
                row.employee_id
                for row in rows
                if row.employee_id
            ]
        )
    }

    preview_rows = [
        (row, accounts.get(row.employee_id))
        for row in rows
    ]

    matched_count = sum(
        1
        for row in rows
        if row.match_status == PTOImportRow.MatchStatus.MATCHED
        and row.employee_id
    )

    skipped_count = len(rows) - matched_count

    has_problems = skipped_count > 0

    return render(
        request,
        "absence/pto_import_preview.html",
        {
            "pto_import": pto_import,
            "preview_rows": preview_rows,
            "matched_count": matched_count,
            "skipped_count": skipped_count,
            "has_problems": has_problems,
            "all_employees": (
                User.objects.filter(
                    is_active=True,
                    employee_profile__isnull=False,
                ).order_by(
                    "last_name",
                    "first_name",
                    "username",
                )
                if has_problems
                else User.objects.none()
            ),
        },
    )


@login_required
def pto_import_match(request, row_id):
    if not can_import_pto(request.user):
        return HttpResponseForbidden("Management Staff access required.")
    if request.method != "POST":
        return HttpResponseForbidden("POST required")
    row = get_object_or_404(PTOImportRow, pk=row_id, pto_import__status=PTOImport.Status.PREVIEW)
    employee = get_object_or_404(User, pk=request.POST.get("employee_id"), is_active=True, employee_profile__isnull=False)
    row.employee = employee
    row.match_status = PTOImportRow.MatchStatus.MATCHED
    row.match_message = "Matched manually."
    row.save(update_fields=["employee", "match_status", "match_message"])
    messages.success(request, f"Matched {row.employee_name} to {employee.get_full_name() or employee.username}.")
    return redirect("pto_import_preview", pk=row.pto_import_id)


@login_required
@transaction.atomic
def pto_import_apply(request, pk):
    if not can_import_pto(request.user):
        return HttpResponseForbidden("Management Staff access required.")
    if request.method != "POST":
        return HttpResponseForbidden("POST required")
    pto_import = get_object_or_404(PTOImport, pk=pk)
    try:
        apply_pto_import(pto_import, request.user)
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            "PTO report applied successfully. Only matched employees were imported."
        )
    return redirect("pto_import_preview", pk=pto_import.pk)


@login_required
def absence_artifact_download(request, artifact_id):
    artifact = get_object_or_404(AbsenceArtifact.objects.select_related("request__employee", "request__manager"), pk=artifact_id)
    if not can_view_absence_request(request.user, artifact.request):
        raise Http404
    path = Path(artifact.file_path)
    if not path.exists() or not path.is_file():
        raise Http404("Archived PDF is not available on the configured file server.")
    return FileResponse(path.open("rb"), as_attachment=True, filename=artifact.filename, content_type="application/pdf")
