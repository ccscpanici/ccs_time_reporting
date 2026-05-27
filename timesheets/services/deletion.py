from django.utils import timezone
from ..models import Timesheet


def delete_or_void_timesheet(timesheet, user, reason=""):
    if timesheet.status in {Timesheet.Status.APPROVED, Timesheet.Status.INVOICED} and not user.is_staff:
        raise PermissionError("Approved or invoiced timesheets cannot be deleted by regular users.")

    timesheet.deleted_at = timezone.now()
    timesheet.deleted_by = user
    timesheet.delete_reason = reason or ""
    if timesheet.status in {Timesheet.Status.SUBMITTED, Timesheet.Status.REOPENED, Timesheet.Status.APPROVED, Timesheet.Status.INVOICED}:
        timesheet.status = Timesheet.Status.VOID
    timesheet.save(update_fields=["deleted_at", "deleted_by", "delete_reason", "status", "updated_at"])
    return timesheet
