from django.db import transaction
from django.utils import timezone
from ..models import Timesheet


@transaction.atomic
def reopen_timesheet(timesheet, user, reason):
    timesheet = Timesheet.objects.select_for_update().get(pk=timesheet.pk)
    if timesheet.deleted_at:
        raise ValueError("Deleted or voided timesheets cannot be reopened.")
    if timesheet.employee_id != user.id:
        raise PermissionError("You can only reopen your own timesheets.")
    if timesheet.status != Timesheet.Status.SUBMITTED:
        raise ValueError("Only submitted timesheets can be reopened.")
    if not reason or not reason.strip():
        raise ValueError("A reopen reason is required.")

    timesheet.status = Timesheet.Status.REOPENED
    timesheet.reopened_at = timezone.now()
    timesheet.reopened_by = user
    timesheet.reopen_reason = reason.strip()
    timesheet.save(update_fields=["status", "reopened_at", "reopened_by", "reopen_reason", "updated_at"])
    return timesheet


@transaction.atomic
def approve_timesheet(timesheet, user):
    timesheet = Timesheet.objects.select_for_update().get(pk=timesheet.pk)
    if timesheet.deleted_at:
        raise ValueError("Deleted or voided timesheets cannot be approved.")
    if timesheet.status != Timesheet.Status.SUBMITTED:
        raise ValueError("Only submitted timesheets can be approved.")

    timesheet.status = Timesheet.Status.APPROVED
    timesheet.approved_at = timezone.now()
    timesheet.approved_by = user
    timesheet.save(update_fields=["status", "approved_at", "approved_by", "updated_at"])
    return timesheet


@transaction.atomic
def mark_timesheet_invoiced(timesheet, user):
    timesheet = Timesheet.objects.select_for_update().get(pk=timesheet.pk)
    if timesheet.deleted_at:
        raise ValueError("Deleted or voided timesheets cannot be marked invoiced.")
    if timesheet.status != Timesheet.Status.APPROVED:
        raise ValueError("Only approved timesheets can be marked invoiced.")

    timesheet.status = Timesheet.Status.INVOICED
    timesheet.invoiced_at = timezone.now()
    timesheet.invoiced_by = user
    timesheet.save(update_fields=["status", "invoiced_at", "invoiced_by", "updated_at"])
    return timesheet
