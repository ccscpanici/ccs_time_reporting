from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from timesheets.management.commands.process_email_queue import Command
from timesheets.models import EmailJob, Timesheet
from timesheets.services.email_queue import (
    MAX_ATTEMPTS,
    process_email_job,
    queue_email_job,
)


class EmailQueueTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="email_queue_test",
            email="test@example.com",
            password="test-password",
            first_name="Email",
            last_name="Queue",
        )

        self.timesheet = Timesheet.objects.create(
            employee=self.user,
            week_start="2026-09-27",
        )

    def test_queue_email_job_creates_job_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            queue_email_job(
                job_type=EmailJob.JobType.TIMESHEET_APPROVED_EMPLOYEE,
                timesheet=self.timesheet,
                actor=self.user,
            )

        job = EmailJob.objects.get()

        self.assertEqual(
            job.job_type,
            EmailJob.JobType.TIMESHEET_APPROVED_EMPLOYEE,
        )
        self.assertEqual(job.timesheet, self.timesheet)
        self.assertEqual(job.actor, self.user)
        self.assertEqual(job.status, EmailJob.Status.PENDING)
        self.assertEqual(job.attempts, 0)

    @patch("timesheets.services.email_queue._dispatch_job")
    def test_process_email_job_marks_job_sent(self, dispatch):
        job = EmailJob.objects.create(
            job_type=EmailJob.JobType.TIMESHEET_APPROVED_EMPLOYEE,
            timesheet=self.timesheet,
            actor=self.user,
        )

        result = process_email_job(job)

        job.refresh_from_db()

        self.assertTrue(result)
        self.assertEqual(job.status, EmailJob.Status.SENT)
        self.assertEqual(job.attempts, 1)
        self.assertIsNotNone(job.sent_at)
        self.assertEqual(job.last_error, "")
        dispatch.assert_called_once()

    @patch(
        "timesheets.services.email_queue._dispatch_job",
        side_effect=RuntimeError("SMTP unavailable"),
    )
    def test_process_email_job_schedules_retry(self, dispatch):
        job = EmailJob.objects.create(
            job_type=EmailJob.JobType.TIMESHEET_APPROVED_EMPLOYEE,
            timesheet=self.timesheet,
            actor=self.user,
        )

        before = timezone.now()

        result = process_email_job(job)

        job.refresh_from_db()

        self.assertFalse(result)
        self.assertEqual(job.status, EmailJob.Status.PENDING)
        self.assertEqual(job.attempts, 1)
        self.assertEqual(job.last_error, "SMTP unavailable")

        expected = before + timedelta(minutes=1)

        self.assertAlmostEqual(
            job.next_attempt_at.timestamp(),
            expected.timestamp(),
            delta=2,
        )

        dispatch.assert_called_once()

    @patch(
        "timesheets.services.email_queue._dispatch_job",
        side_effect=RuntimeError("SMTP unavailable"),
    )
    def test_process_email_job_marks_job_failed_after_max_attempts(
        self,
        dispatch,
    ):
        job = EmailJob.objects.create(
            job_type=EmailJob.JobType.TIMESHEET_APPROVED_EMPLOYEE,
            timesheet=self.timesheet,
            actor=self.user,
            attempts=MAX_ATTEMPTS - 1,
        )

        result = process_email_job(job)

        job.refresh_from_db()

        self.assertFalse(result)
        self.assertEqual(job.status, EmailJob.Status.FAILED)
        self.assertEqual(job.attempts, MAX_ATTEMPTS)
        self.assertEqual(job.last_error, "SMTP unavailable")

        dispatch.assert_called_once()

    def test_claim_next_job_recovers_stale_processing_job(self):
        stale_started_at = timezone.now() - timedelta(minutes=11)

        job = EmailJob.objects.create(
            job_type=EmailJob.JobType.TIMESHEET_APPROVED_EMPLOYEE,
            timesheet=self.timesheet,
            actor=self.user,
            status=EmailJob.Status.PROCESSING,
            started_at=stale_started_at,
        )

        claimed_job = Command._claim_next_job()

        job.refresh_from_db()

        self.assertIsNotNone(claimed_job)
        self.assertEqual(claimed_job.pk, job.pk)
        self.assertEqual(job.status, EmailJob.Status.PROCESSING)
        self.assertGreater(job.started_at, stale_started_at)
        self.assertEqual(
            job.last_error,
            "Worker interrupted while processing; retrying.",
        )
