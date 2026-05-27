import threading
import tempfile
import zipfile
import shutil
from datetime import date, timedelta
from pathlib import Path
from django.contrib import messages
from django.core.files import File
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .forms import TimesheetBulkZipImportForm, TimesheetCreateForm, TimesheetDeleteForm, TimesheetImportForm, TimesheetReopenForm, TimesheetSubmitForm
from .models import BulkImportJob, Expense, Job, MileageRate, PartEntry, TimeEntry, Timesheet, TimesheetReceipt, TimesheetSubmissionArtifact, WorkCode, TimesheetImport
from .services.deletion import delete_or_void_timesheet
from .services.grid import build_timesheet_grid, is_blank_row
from .services.helpers import as_decimal
from .services.importer import import_timesheet_upload
from .services.submission import create_timesheet_artifact, submit_timesheet
from .services.status import approve_timesheet, mark_timesheet_invoiced, reopen_timesheet
from .permissions import is_management_staff



def _safe_zip_members(zip_file):
    """Return safe XLSX members from a ZIP file.

    Skips directories, hidden Excel temp files, non-xlsx files, and unsafe paths.
    """
    members = []
    for member in zip_file.infolist():
        name = member.filename

        if member.is_dir():
            continue

        normalized = name.replace("\\", "/")
        filename = Path(normalized).name

        if not filename:
            continue

        if filename.startswith("~$"):
            continue

        if not filename.lower().endswith(".xlsx"):
            continue

        path = Path(normalized)

        if path.is_absolute() or ".." in path.parts:
            continue

        members.append(member)

    return members



def _apply_bulk_import_status(timesheet, user, *, mark_submitted=False, mark_approved=False):
    """Apply optional submitted/approved state after a bulk import."""
    if not mark_submitted and not mark_approved:
        return timesheet

    now = timezone.now()
    update_fields = ["status", "updated_at"]

    if mark_submitted or mark_approved:
        timesheet.status = Timesheet.Status.SUBMITTED
        timesheet.submitted_at = now
        timesheet.submitted_by = user
        update_fields.extend(["submitted_at", "submitted_by"])

    if mark_approved:
        timesheet.status = Timesheet.Status.APPROVED
        timesheet.approved_at = now
        timesheet.approved_by = user
        update_fields.extend(["approved_at", "approved_by"])

    timesheet.save(update_fields=update_fields)
    return timesheet



def _run_bulk_import_job(job_id, mark_submitted=False, mark_approved=False):
    job = BulkImportJob.objects.get(pk=job_id)
    job.status = "running"
    job.save(update_fields=["status"])

    results = []

    try:
        with zipfile.ZipFile(job.uploaded_zip.path) as archive:
            members = _safe_zip_members(archive)
            job.total_files = len(members)
            job.save(update_fields=["total_files"])

            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)

                for member in members:
                    original_name = Path(member.filename.replace("\\", "/")).name
                    result = {
                        "filename": original_name,
                        "status": "pending",
                        "message": "",
                    }

                    try:
                        extract_path = tmp_path / original_name

                        with archive.open(member) as source, open(extract_path, "wb") as target:
                            shutil.copyfileobj(source, target)

                        with open(extract_path, "rb") as workbook_file:
                            upload = TimesheetImport(employee=job.employee)
                            upload.uploaded_file.save(original_name, File(workbook_file), save=True)

                        timesheet = import_timesheet_upload(upload)

                        _apply_bulk_import_status(
                            timesheet,
                            job.employee,
                            mark_submitted=mark_submitted,
                            mark_approved=mark_approved,
                        )

                        result["status"] = "imported"
                        result["message"] = upload.message or f"Imported week of {timesheet.week_start}."

                        job.imported_files += 1

                    except Exception as exc:
                        result["status"] = "failed"
                        result["message"] = str(exc)
                        job.failed_files += 1

                    results.append(result)
                    job.processed_files += 1
                    job.results_json = results
                    job.save(update_fields=["processed_files", "imported_files", "failed_files", "results_json"])

        job.status = "completed"
        job.completed_at = timezone.now()
        job.results_json = results
        job.save(update_fields=["status", "completed_at", "results_json"])

    except Exception as exc:
        job.status = "failed"
        job.results_json = [{"status":"failed","message":str(exc)}]
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "results_json", "completed_at"])


def sunday_for(d):
    # Company timesheet weeks start on Sunday.
    return d - timedelta(days=(d.weekday() + 1) % 7)


def attachment_response(artifact):
    """Return a saved submission artifact as a real browser download."""

    timesheet = artifact.timesheet
    user = timesheet.employee

    initials = (
        f"{(user.first_name or '')[:1]}"
        f"{(user.last_name or '')[:1]}"
    ).upper()

    if not initials.strip():
        initials = user.get_username()[:2].upper()

    suffix = Path(artifact.file.name).suffix.lower()
    filename = f"{timesheet.week_start:%Y%m%d}_{initials}{suffix}"

    if suffix == ".pdf":
        content_type = "application/pdf"
    elif suffix == ".xlsx":
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        content_type = "application/octet-stream"

    # Prefer FileResponse from the storage path. It is the most reliable way to
    # make browsers treat this as a downloaded file instead of an HTML response.
    try:
        response = FileResponse(
            artifact.file.open("rb"),
            as_attachment=True,
            filename=filename,
            content_type=content_type,
        )
    except Exception:
        # Some storage backends do not support a direct file handle. Fall back to
        # reading bytes while still forcing attachment headers.
        with artifact.file.open("rb") as file_obj:
            file_bytes = file_obj.read()
        response = HttpResponse(file_bytes, content_type=content_type)
        response["Content-Length"] = str(len(file_bytes))
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def get_timesheet_for_request_user(request, pk):
    queryset = Timesheet.objects.filter(pk=pk, deleted_at__isnull=True)
    if not is_management_staff(request.user):
        queryset = queryset.filter(employee=request.user)
    return get_object_or_404(queryset)


@login_required
def timesheet_list(request):
    timesheet_qs = Timesheet.objects.filter(
        employee=request.user,
        deleted_at__isnull=True,
    ).order_by("-week_start", "-created_at")

    paginator = Paginator(timesheet_qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "timesheets/list.html", {
        "timesheets": page_obj,
        "page_obj": page_obj,
    })


@login_required
def timesheet_create(request):
    initial = {"week_start": sunday_for(date.today()), "entries_per_day": 5}
    if request.method == "POST":
        form = TimesheetCreateForm(request.POST)
        if form.is_valid():
            week_start = form.cleaned_data["week_start"]
            entries_per_day = form.cleaned_data["entries_per_day"]

            timesheet, created = Timesheet.objects.get_or_create(
                employee=request.user,
                week_start=week_start,
                defaults={
                    "entries_per_day": entries_per_day,
                    "template_entries_per_day": 5,
                    "mileage_rate": MileageRate.rate_for_date(week_start),
                    "status": Timesheet.Status.DRAFT,
                },
            )

            if not created and timesheet.deleted_at is not None:
                # Re-open a soft-deleted draft for this week instead of failing on the unique constraint.
                timesheet.deleted_at = None
                timesheet.deleted_by = None
                timesheet.delete_reason = ""
                timesheet.status = Timesheet.Status.DRAFT
                timesheet.entries_per_day = entries_per_day
                timesheet.save(update_fields=[
                    "deleted_at",
                    "deleted_by",
                    "delete_reason",
                    "status",
                    "entries_per_day",
                    "updated_at",
                ])
                created = True

            if created:
                messages.success(request, f"Created timesheet for week of {timesheet.week_start:%m/%d/%Y}.")
            else:
                messages.info(request, f"Opened existing timesheet for week of {timesheet.week_start:%m/%d/%Y}.")

            return redirect("timesheet_edit", pk=timesheet.pk)
    else:
        form = TimesheetCreateForm(initial=initial)
    return render(request, "timesheets/create.html", {"form": form})


@login_required
def timesheet_detail(request, pk):
    timesheet = get_timesheet_for_request_user(request, pk)
    grid = build_timesheet_grid(timesheet)
    return render(request, "timesheets/detail.html", {"timesheet": timesheet, "grid": grid})


@login_required
def timesheet_edit(request, pk):
    timesheet = get_object_or_404(Timesheet, pk=pk, employee=request.user, deleted_at__isnull=True)
    if not timesheet.can_edit:
        messages.error(request, "Only draft, rejected, or reopened timesheets can be edited.")
        return redirect(timesheet)

    work_codes = WorkCode.objects.filter(active=True).order_by("display_order", "code")

    if request.method == "POST":
        entries_per_day = int(request.POST.get("entries_per_day") or timesheet.entries_per_day or 5)
        timesheet.entries_per_day = max(5, min(entries_per_day, 25))
        timesheet.save(update_fields=["entries_per_day", "updated_at"])

        for work_date in timesheet.week_dates:
            day_key = work_date.isoformat()
            overnight_stay = request.POST.get(f"overnight_{day_key}") == "on"
            for row_order in range(1, timesheet.entries_per_day + 1):
                prefix = f"entry_{day_key}_{row_order}"
                row = {
                    "job_number": request.POST.get(f"{prefix}_job_number", "").strip(),
                    "work_code": request.POST.get(f"{prefix}_work_code"),
                    "regular_hours": request.POST.get(f"{prefix}_regular_hours"),
                    "overtime_hours": request.POST.get(f"{prefix}_overtime_hours"),
                    "doubletime_hours": request.POST.get(f"{prefix}_doubletime_hours"),
                    "description": request.POST.get(f"{prefix}_description", "").strip(),
                }
                expense_row = {
                    "miles": request.POST.get(f"{prefix}_expense_miles"),
                    "per_diem_food": request.POST.get(f"{prefix}_expense_per_diem_food"),
                    "air_fare": request.POST.get(f"{prefix}_expense_air_fare"),
                    "hotel": request.POST.get(f"{prefix}_expense_hotel"),
                    "tolls_parking": request.POST.get(f"{prefix}_expense_tolls_parking"),
                    "rental_car_fuel": request.POST.get(f"{prefix}_expense_rental_car_fuel"),
                    "business_meals": request.POST.get(f"{prefix}_expense_business_meals"),
                    "other_expense": request.POST.get(f"{prefix}_expense_other_expense"),
                    "explanation_of_expenses": request.POST.get(f"{prefix}_expense_explanation_of_expenses", "").strip(),
                }
                part_row = {
                    "ee_stock_job_number": request.POST.get(f"{prefix}_part_ee_stock_job_number", "").strip(),
                    "quantity": request.POST.get(f"{prefix}_part_quantity"),
                    "part_description_part_number": request.POST.get(f"{prefix}_part_description_part_number", "").strip(),
                    "additional_notes_for_customer": request.POST.get(f"{prefix}_part_additional_notes_for_customer", "").strip(),
                    "reorder_part": request.POST.get(f"{prefix}_part_reorder_part") == "on",
                }

                qs = TimeEntry.objects.filter(timesheet=timesheet, work_date=work_date, row_order=row_order)
                expense_is_blank = not any(expense_row.get(key) for key in expense_row)
                part_is_blank = not any([
                    part_row["ee_stock_job_number"],
                    part_row["quantity"],
                    part_row["part_description_part_number"],
                    part_row["additional_notes_for_customer"],
                    part_row["reorder_part"],
                ])
                if is_blank_row(row) and expense_is_blank and part_is_blank:
                    qs.delete()
                    continue

                job = Job.objects.filter(job_number__iexact=row["job_number"]).first() if row["job_number"] else None
                work_code = WorkCode.objects.filter(pk=row["work_code"]).first() if row["work_code"] else None
                entry, _created = TimeEntry.objects.update_or_create(
                    timesheet=timesheet,
                    work_date=work_date,
                    row_order=row_order,
                    defaults={
                        "job_number": row["job_number"],
                        "job": job,
                        "work_code": work_code,
                        "regular_hours": as_decimal(row["regular_hours"]),
                        "overtime_hours": as_decimal(row["overtime_hours"]),
                        "doubletime_hours": as_decimal(row["doubletime_hours"]),
                        "overnight_stay": overnight_stay,
                        "description": row["description"],
                    },
                )

                if expense_is_blank:
                    Expense.objects.filter(time_entry=entry).delete()
                else:
                    Expense.objects.update_or_create(
                        time_entry=entry,
                        defaults={
                            "miles": as_decimal(expense_row["miles"]),
                            "per_diem_food": as_decimal(expense_row["per_diem_food"]),
                            "air_fare": as_decimal(expense_row["air_fare"]),
                            "hotel": as_decimal(expense_row["hotel"]),
                            "tolls_parking": as_decimal(expense_row["tolls_parking"]),
                            "rental_car_fuel": as_decimal(expense_row["rental_car_fuel"]),
                            "business_meals": as_decimal(expense_row["business_meals"]),
                            "other_expense": as_decimal(expense_row["other_expense"]),
                            "explanation_of_expenses": expense_row["explanation_of_expenses"],
                        },
                    )

                if part_is_blank:
                    PartEntry.objects.filter(time_entry=entry).delete()
                else:
                    PartEntry.objects.update_or_create(
                        time_entry=entry,
                        defaults={
                            "ee_stock_job_number": part_row["ee_stock_job_number"],
                            "quantity": as_decimal(part_row["quantity"]),
                            "part_description_part_number": part_row["part_description_part_number"],
                            "additional_notes_for_customer": part_row["additional_notes_for_customer"],
                            "reorder_part": part_row["reorder_part"],
                        },
                    )

        messages.success(request, "Timesheet saved.")
        return redirect(timesheet)

    grid = build_timesheet_grid(timesheet)
    return render(request, "timesheets/edit.html", {"timesheet": timesheet, "grid": grid, "work_codes": work_codes})




@login_required
def timesheet_bulk_zip_upload(request):
    if request.method == "POST":
        form = TimesheetBulkZipImportForm(request.POST, request.FILES)

        if form.is_valid():
            job = BulkImportJob.objects.create(
                employee=request.user,
                uploaded_zip=form.cleaned_data["zip_file"],
            )

            thread = threading.Thread(
                target=_run_bulk_import_job,
                args=(
                    job.pk,
                    form.cleaned_data.get("mark_submitted", False),
                    form.cleaned_data.get("mark_approved", False),
                ),
                daemon=True,
            )
            thread.start()

            return redirect("timesheet_bulk_zip_upload_status", job_pk=job.pk)
    else:
        form = TimesheetBulkZipImportForm()

    return render(request, "timesheets/bulk_zip_upload.html", {"form": form})


@login_required
def timesheet_bulk_zip_upload_status(request, job_pk):
    job = get_object_or_404(BulkImportJob, pk=job_pk, employee=request.user)
    return render(request, "timesheets/bulk_zip_upload_status.html", {"job": job})


@login_required
def timesheet_bulk_zip_upload_status_api(request, job_pk):
    job = get_object_or_404(BulkImportJob, pk=job_pk, employee=request.user)

    return JsonResponse({
        "status": job.status,
        "total_files": job.total_files,
        "processed_files": job.processed_files,
        "imported_files": job.imported_files,
        "failed_files": job.failed_files,
        "results": job.results_json,
        "completed": job.status in {"completed", "failed"},
    })



@login_required
def timesheet_upload(request):
    if request.method == "POST":
        form = TimesheetImportForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save(commit=False)
            upload.employee = request.user
            upload.save()
            try:
                timesheet = import_timesheet_upload(upload)
            except Exception as exc:
                upload.status = "failed"
                upload.message = str(exc)
                upload.save(update_fields=["status", "message"])
                messages.error(request, f"Import failed: {exc}")
                return redirect("timesheet_upload")
            messages.success(request, upload.message)
            return redirect(timesheet)
    else:
        form = TimesheetImportForm()
    return render(request, "timesheets/upload.html", {"form": form})


@login_required
def timesheet_download(request, pk):
    """Download the current timesheet without changing its status."""
    timesheet = get_timesheet_for_request_user(request, pk)
    requested_format = request.GET.get("format") or Timesheet.ExportFormat.EXCEL

    if requested_format not in {Timesheet.ExportFormat.EXCEL, Timesheet.ExportFormat.PDF}:
        requested_format = Timesheet.ExportFormat.EXCEL

    # Excel cannot represent more than the official template row limit.
    # In that case, fall back to PDF instead of failing the download.
    if requested_format == Timesheet.ExportFormat.EXCEL and not timesheet.can_export_excel:
        requested_format = Timesheet.ExportFormat.PDF

    try:
        artifact = create_timesheet_artifact(
            timesheet=timesheet,
            created_by=request.user,
            export_format=requested_format,
            submitted=False,
        )
    except Exception as exc:
        messages.error(request, f"Download failed: {exc}")
        return redirect(timesheet)

    return redirect("timesheet_submitted_download", artifact_pk=artifact.pk)


@login_required
def timesheet_submit(request, pk):
    timesheet = get_object_or_404(Timesheet, pk=pk, employee=request.user, deleted_at__isnull=True)
    if not timesheet.can_submit:
        messages.error(request, "Only draft, rejected, or reopened timesheets can be submitted.")
        return redirect(timesheet)
    if request.method == "POST":
        form = TimesheetSubmitForm(request.POST, timesheet=timesheet)
        if form.is_valid():
            requested_format = form.cleaned_data["export_format"]
        else:
            # Be defensive: if the browser did not send a selected radio value,
            # choose the safest valid export instead of returning the HTML form.
            requested_format = Timesheet.ExportFormat.PDF if not timesheet.can_export_excel else Timesheet.ExportFormat.EXCEL

        try:
            artifact = submit_timesheet(timesheet, request.user, requested_format)
        except Exception as exc:
            messages.error(request, f"Submit failed: {exc}")
            return redirect(timesheet)
        # end try

        return redirect("timesheet_submitted_download", artifact_pk=artifact.pk)
    # end if

    form = TimesheetSubmitForm(timesheet=timesheet)
    return render(request, "timesheets/submit.html", {"timesheet": timesheet, "form": form})


@login_required
def timesheet_submitted_download(request, artifact_pk):
    """Intermediate page that starts download then redirects."""
    artifact = get_object_or_404(
        TimesheetSubmissionArtifact.objects.select_related("timesheet", "timesheet__employee"),
        pk=artifact_pk,
    )

    if artifact.timesheet.employee_id != request.user.id and not is_management_staff(request.user):
        raise Http404()

    return render(
        request,
        "timesheets/submitted_download.html",
        {
            "artifact": artifact,
            "timesheet": artifact.timesheet,
            "redirect_url": artifact.timesheet.get_absolute_url(),
        },
    )


@login_required
def timesheet_artifact_download(request, artifact_pk):
    artifact = get_object_or_404(
        TimesheetSubmissionArtifact.objects.select_related("timesheet", "timesheet__employee"),
        pk=artifact_pk,
    )

    # Regular users may only download their own submitted artifacts.
    # Management staff can download artifacts for reviewed timesheets.
    if artifact.timesheet.employee_id != request.user.id and not is_management_staff(request.user):
        raise Http404()

    return attachment_response(artifact)



@login_required
def timesheet_receipt_upload(request, pk):
    timesheet = get_object_or_404(Timesheet, pk=pk, employee=request.user, deleted_at__isnull=True)

    if not timesheet.can_edit:
        messages.error(request, "Receipts can only be uploaded while the timesheet is editable.")
        return redirect(timesheet)

    if request.method != "POST":
        return redirect(timesheet)

    files = request.FILES.getlist("receipt_files")
    description = request.POST.get("receipt_description", "").strip()

    if not files:
        messages.error(request, "Please choose at least one receipt file to upload.")
        return redirect(timesheet)

    for uploaded_file in files:
        TimesheetReceipt.objects.create(
            timesheet=timesheet,
            uploaded_by=request.user,
            file=uploaded_file,
            original_filename=uploaded_file.name,
            description=description,
        )

    messages.success(request, f"Uploaded {len(files)} receipt file(s).")
    return redirect(timesheet)


@login_required
def timesheet_receipt_download(request, receipt_pk):
    receipt = get_object_or_404(
        TimesheetReceipt.objects.select_related("timesheet", "timesheet__employee"),
        pk=receipt_pk,
    )

    if receipt.timesheet.employee_id != request.user.id and not is_management_staff(request.user):
        raise Http404()

    response = FileResponse(
        receipt.file.open("rb"),
        as_attachment=False,
        filename=receipt.filename(),
    )
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def timesheet_receipt_delete(request, receipt_pk):
    receipt = get_object_or_404(
        TimesheetReceipt.objects.select_related("timesheet", "timesheet__employee"),
        pk=receipt_pk,
    )

    if receipt.timesheet.employee_id != request.user.id:
        raise Http404()

    if not receipt.timesheet.can_edit:
        messages.error(request, "Receipts can only be deleted while the timesheet is editable.")
        return redirect(receipt.timesheet)

    if request.method != "POST":
        return redirect(receipt.timesheet)

    timesheet = receipt.timesheet
    receipt.file.delete(save=False)
    receipt.delete()

    messages.success(request, "Receipt deleted.")
    return redirect(timesheet)


@login_required
def timesheet_reopen(request, pk):
    timesheet = get_object_or_404(Timesheet, pk=pk, employee=request.user, deleted_at__isnull=True)
    if not timesheet.can_reopen:
        messages.error(request, "Only submitted timesheets can be reopened.")
        return redirect(timesheet)

    if request.method == "POST":
        form = TimesheetReopenForm(request.POST)
        if form.is_valid():
            try:
                reopen_timesheet(timesheet, request.user, form.cleaned_data["reason"])
            except Exception as exc:
                messages.error(request, f"Reopen failed: {exc}")
                return redirect(timesheet)
            messages.success(request, "Timesheet reopened. You can now make corrections and resubmit it.")
            return redirect("timesheet_edit", pk=timesheet.pk)
    else:
        form = TimesheetReopenForm()
    return render(request, "timesheets/reopen.html", {"timesheet": timesheet, "form": form})


@login_required
def timesheet_approve(request, pk):
    if not is_management_staff(request.user):
        messages.error(request, "Only management staff can approve timesheets.")
        return redirect("timesheet_list")
    timesheet = get_timesheet_for_request_user(request, pk)
    if request.method != "POST":
        return redirect(timesheet)
    try:
        approve_timesheet(timesheet, request.user)
    except Exception as exc:
        messages.error(request, f"Approve failed: {exc}")
    else:
        messages.success(request, "Timesheet approved.")
    return redirect(timesheet)


@login_required
def timesheet_mark_invoiced(request, pk):
    if not is_management_staff(request.user):
        messages.error(request, "Only management staff can mark timesheets invoiced.")
        return redirect("timesheet_list")
    timesheet = get_timesheet_for_request_user(request, pk)
    if request.method != "POST":
        return redirect(timesheet)
    try:
        mark_timesheet_invoiced(timesheet, request.user)
    except Exception as exc:
        messages.error(request, f"Mark invoiced failed: {exc}")
    else:
        messages.success(request, "Timesheet marked invoiced.")
    return redirect(timesheet)


@login_required
def timesheet_delete(request, pk):
    timesheet = get_object_or_404(Timesheet, pk=pk, employee=request.user, deleted_at__isnull=True)
    if request.method == "POST":
        form = TimesheetDeleteForm(request.POST)
        if form.is_valid():
            try:
                delete_or_void_timesheet(timesheet, request.user, form.cleaned_data["reason"])
            except Exception as exc:
                messages.error(request, f"Delete failed: {exc}")
                return redirect(timesheet)
            messages.success(request, "Timesheet deleted." if timesheet.status in {Timesheet.Status.DRAFT, Timesheet.Status.REJECTED} else "Timesheet voided.")
            return redirect("timesheet_list")
    else:
        form = TimesheetDeleteForm()
    return render(request, "timesheets/delete.html", {"timesheet": timesheet, "form": form})
