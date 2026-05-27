from pathlib import Path
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from ..models import Timesheet, TimesheetSubmissionArtifact
from .exporter import build_submission_attachment


def create_timesheet_artifact(timesheet, created_by, export_format, *, submitted=False):
    """Generate an Excel/PDF timesheet file and save it as a reusable artifact.

    This is used by both:
    - Download: creates an artifact without changing timesheet status.
    - Submit and Download: creates an artifact before marking the sheet submitted.
    """
    if export_format == Timesheet.ExportFormat.EXCEL and not timesheet.can_export_excel:
        raise ValueError(
            "Excel export only works when each date has 5 or fewer time entries. Use PDF Report instead."
        )

    generated_path = Path(build_submission_attachment(timesheet, export_format))
    if not generated_path.exists():
        raise FileNotFoundError(f"Generated timesheet file was not found: {generated_path}")

    file_type = "xlsx" if generated_path.suffix.lower() == ".xlsx" else "pdf"
    artifact = TimesheetSubmissionArtifact(
        timesheet=timesheet,
        file_type=file_type,
        export_format=export_format,
        created_by=created_by,
        submitted=submitted,
    )
    artifact.file.save(generated_path.name, ContentFile(generated_path.read_bytes()), save=True)
    return artifact


@transaction.atomic
def submit_timesheet(timesheet, submitted_by, export_format):
    """Mark a timesheet submitted, generate the selected file, and store it as an artifact.

    Email automation will be added later. For now the view returns the saved
    artifact file to the browser as a download. Storing the artifact gives us a
    historical copy of exactly what was submitted.
    """
    timesheet = Timesheet.objects.select_for_update().get(pk=timesheet.pk)
    if timesheet.deleted_at:
        raise ValueError("Deleted or voided timesheets cannot be submitted.")
    if timesheet.status in {Timesheet.Status.SUBMITTED, Timesheet.Status.APPROVED, Timesheet.Status.INVOICED, Timesheet.Status.VOID}:
        raise ValueError("Only draft, rejected, or reopened timesheets can be submitted.")
    if not timesheet.entries.exists():
        raise ValueError("Cannot submit an empty timesheet.")
    if export_format == Timesheet.ExportFormat.EXCEL and not timesheet.can_export_excel:
        raise ValueError("Excel export only works when each date has 5 or fewer time entries. Use PDF Report instead.")

    # Generate before changing state so export failures do not leave the sheet submitted.
    artifact = create_timesheet_artifact(
        timesheet=timesheet,
        created_by=submitted_by,
        export_format=export_format,
        submitted=True,
    )

    timesheet.status = Timesheet.Status.SUBMITTED
    timesheet.submitted_at = timezone.now()
    timesheet.submitted_by = submitted_by
    timesheet.submission_export_format = export_format
    # Keep the reopen audit trail, but clear approval/invoicing fields on resubmission.
    timesheet.approved_at = None
    timesheet.approved_by = None
    timesheet.invoiced_at = None
    timesheet.invoiced_by = None
    timesheet.save(update_fields=[
        "status",
        "submitted_at",
        "submitted_by",
        "submission_export_format",
        "approved_at",
        "approved_by",
        "invoiced_at",
        "invoiced_by",
        "updated_at",
    ])

    return artifact
