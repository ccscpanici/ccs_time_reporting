"""Service-layer operations for email queue workflows.

Business rules live here so views and commands can share the same behavior.
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from ..models import EmailJob
from .notifications import (
    send_employee_reopen_approved_email,
    send_employee_reopen_rejected_email,
    send_employee_timesheet_approved_email,
    send_employee_timesheet_rejected_email,
    send_reopened_admin_notification,
    send_timesheet_approved_email,
    send_timesheet_reopen_request_email,
    send_timesheet_submitted_supervisor_email,
)

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5

RETRY_DELAYS = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(hours=1),
)


def queue_email_job(*, job_type, timesheet, actor=None, payload=None):
    """
    Queue an email job after the surrounding database transaction commits.

    This prevents a worker from seeing the job before the timesheet changes
    that caused the notification have committed.
    """
    payload = payload or {}

    def create_job():
        """Create job for the current workflow."""
        job = EmailJob.objects.create(
            job_type=job_type,
            timesheet=timesheet,
            actor=actor,
            payload=payload,
        )

        logger.info(
            "Queued email job %s (%s) for timesheet %s",
            job.pk,
            job.job_type,
            timesheet.pk,
        )

    transaction.on_commit(create_job)


def _dispatch_job(job):
    """
    Execute the notification represented by an EmailJob.
    """
    if job.job_type == EmailJob.JobType.TIMESHEET_APPROVED_ADMIN:
        send_timesheet_approved_email(
            job.timesheet,
            job.actor,
        )
        return

    if job.job_type == EmailJob.JobType.TIMESHEET_APPROVED_EMPLOYEE:
        send_employee_timesheet_approved_email(
            job.timesheet,
            job.actor,
        )
        return

    if job.job_type == EmailJob.JobType.TIMESHEET_REJECTED_EMPLOYEE:
        send_employee_timesheet_rejected_email(
            job.timesheet,
            job.actor,
            job.payload.get("reason", ""),
        )
        return

    if job.job_type == EmailJob.JobType.TIMESHEET_SUBMITTED_SUPERVISOR:
        send_timesheet_submitted_supervisor_email(
            job.timesheet,
            job.actor,
        )
        return

    if job.job_type == EmailJob.JobType.TIMESHEET_REOPEN_REQUEST:
        reopen_request_id = job.payload.get("reopen_request_id")
        if not reopen_request_id:
            raise ValueError(
                "Missing reopen_request_id for reopen request email job."
            )

        from ..models import TimesheetReopenRequest

        reopen_request = TimesheetReopenRequest.objects.get(
            pk=reopen_request_id
        )
        send_timesheet_reopen_request_email(reopen_request)
        return

    if job.job_type == EmailJob.JobType.TIMESHEET_REOPENED_ADMIN:
        send_reopened_admin_notification(
            job.timesheet,
            job.actor,
        )
        return

    if job.job_type == EmailJob.JobType.TIMESHEET_REOPEN_APPROVED_EMPLOYEE:
        reopen_request_id = job.payload.get("reopen_request_id")
        if not reopen_request_id:
            raise ValueError(
                "Missing reopen_request_id for reopen approved email job."
            )

        from ..models import TimesheetReopenRequest

        reopen_request = TimesheetReopenRequest.objects.get(
            pk=reopen_request_id
        )
        send_employee_reopen_approved_email(reopen_request)
        return

    if job.job_type == EmailJob.JobType.TIMESHEET_REOPEN_REJECTED_EMPLOYEE:
        reopen_request_id = job.payload.get("reopen_request_id")
        if not reopen_request_id:
            raise ValueError(
                "Missing reopen_request_id for reopen rejected email job."
            )

        from ..models import TimesheetReopenRequest

        reopen_request = TimesheetReopenRequest.objects.get(
            pk=reopen_request_id
        )
        send_employee_reopen_rejected_email(reopen_request)
        return

    raise ValueError(f"Unknown email job type: {job.job_type}")


def _retry_delay(attempts):
    """
    Return the delay before the next attempt.

    Attempts beyond the configured schedule use the final delay.
    """
    index = min(max(attempts - 1, 0), len(RETRY_DELAYS) - 1)
    return RETRY_DELAYS[index]


def process_email_job(job):
    """
    Process one EmailJob.

    Returns True when the email was sent successfully and False when the
    attempt failed.
    """
    job.status = EmailJob.Status.PROCESSING
    job.started_at = timezone.now()
    job.attempts += 1
    job.last_error = ""

    job.save(
        update_fields=[
            "status",
            "started_at",
            "attempts",
            "last_error",
            "updated_at",
        ]
    )

    try:
        _dispatch_job(job)

    except Exception as exc:
        logger.exception(
            "Email job %s failed on attempt %s",
            job.pk,
            job.attempts,
        )

        job.last_error = str(exc)

        if job.attempts >= MAX_ATTEMPTS:
            job.status = EmailJob.Status.FAILED
        else:
            job.status = EmailJob.Status.PENDING
            job.next_attempt_at = timezone.now() + _retry_delay(job.attempts)

        job.save(
            update_fields=[
                "status",
                "next_attempt_at",
                "last_error",
                "updated_at",
            ]
        )

        return False

    job.status = EmailJob.Status.SENT
    job.sent_at = timezone.now()
    job.last_error = ""

    job.save(
        update_fields=[
            "status",
            "sent_at",
            "last_error",
            "updated_at",
        ]
    )

    logger.info(
        "Email job %s sent successfully on attempt %s",
        job.pk,
        job.attempts,
    )

    return True
