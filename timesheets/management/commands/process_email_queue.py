"""Django management command for process email queue."""

import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from timesheets.models import EmailJob
from timesheets.services.email_queue import process_email_job


class Command(BaseCommand):
    """Implement the ``process_email_queue`` Django management command."""
    help = "Process queued email jobs."

    def add_arguments(self, parser):
        """Define command-line options accepted by the ``process_email_queue`` command."""
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process available jobs and exit.",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=2.0,
            help="Seconds to wait when no jobs are available.",
        )

    def handle(self, *args, **options):
        """Execute the ``process_email_queue`` management command."""
        run_once = options["once"]
        sleep_seconds = options["sleep"]

        self.stdout.write("Email queue worker started.")

        while True:
            job = self._claim_next_job()

            if job is None:
                if run_once:
                    return

                time.sleep(sleep_seconds)
                continue

            self.stdout.write(
                f"Processing email job {job.pk}: {job.job_type}"
            )

            process_email_job(job)

    @staticmethod
    def _claim_next_job():
        """Provide the claim next job helper used by the ``process_email_queue`` management command."""
        now = timezone.now()
        stale_before = now - timedelta(minutes=10)

        with transaction.atomic():
            EmailJob.objects.filter(
                status=EmailJob.Status.PROCESSING,
                started_at__lt=stale_before,
            ).update(
                status=EmailJob.Status.PENDING,
                next_attempt_at=now,
                last_error="Worker interrupted while processing; retrying.",
            )

            job = (
                EmailJob.objects
                .select_for_update(skip_locked=True)
                .filter(
                    status=EmailJob.Status.PENDING,
                    next_attempt_at__lte=now,
                )
                .order_by("created_at")
                .first()
            )

            if job is None:
                return None

            job.status = EmailJob.Status.PROCESSING
            job.started_at = now

            job.save(
                update_fields=[
                    "status",
                    "started_at",
                    "updated_at",
                ]
            )

            return job
