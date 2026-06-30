from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from timesheets.models import Customer, Job
from timesheets.services.job_cleanup import (
    cleanup_invalid_job,
    entries_for_invalid_job,
    invalid_job_qs,
    suggest_replacement_jobs,
    valid_replacement_jobs,
)


class Command(BaseCommand):
    help = "Interactively clean up invalid job records with blank descriptions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated, but do not change time entries or delete jobs.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Process at most this many invalid jobs.",
        )
        parser.add_argument(
            "--suggestions",
            type=int,
            default=5,
            help="Number of suggested replacement jobs to show for each invalid job.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        suggestion_count = options["suggestions"]

        jobs = list(invalid_job_qs())
        if limit:
            jobs = jobs[:limit]

        if not jobs:
            self.stdout.write(self.style.SUCCESS("No invalid jobs found."))
            return

        self.stdout.write(f"Found {len(jobs)} invalid job(s).")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: no changes will be saved."))

        for job in jobs:
            self._process_job(job, dry_run=dry_run, suggestion_count=suggestion_count)

    def _process_job(self, job, dry_run=False, suggestion_count=5):
        entries = entries_for_invalid_job(job)
        entry_count = entries.count()
        first_date = entries.order_by("work_date").values_list("work_date", flat=True).first()
        last_date = entries.order_by("-work_date").values_list("work_date", flat=True).first()

        self.stdout.write("")
        self.stdout.write("=" * 72)
        self.stdout.write(f"Invalid job: {job.job_number}")
        self.stdout.write(f"Time entries: {entry_count}")
        self.stdout.write(f"Date range: {first_date or '-'} to {last_date or '-'}")

        samples = list(entries.exclude(description="").order_by("work_date").values_list("description", flat=True)[:5])
        if samples:
            self.stdout.write("Sample descriptions:")
            for sample in samples:
                self.stdout.write(f"  - {sample}")

        suggestions = suggest_replacement_jobs(job.job_number, limit=suggestion_count)
        if suggestions:
            self.stdout.write("Suggested replacements:")
            for score, suggested_job in suggestions:
                self.stdout.write(f"  {score:>3}%  {suggested_job.job_number} - {suggested_job.description}")
        else:
            self.stdout.write("Suggested replacements: none")

        self.stdout.write("")
        self.stdout.write("Enter a valid replacement job number.")
        self.stdout.write("Press Enter with no value to clear this job to internal/no-job work.")
        self.stdout.write("Type 'new' to create/complete this job record and keep entries assigned to it.")
        self.stdout.write("Type 'skip' to leave this invalid job unchanged.")
        self.stdout.write("Type 'quit' to stop.")

        while True:
            replacement_number = input(f"Replacement for {job.job_number}: ").strip()

            if replacement_number.lower() in {"quit", "q", "exit"}:
                raise CommandError("Stopped by user.")

            if replacement_number.lower() in {"skip", "s"}:
                self.stdout.write(self.style.WARNING(f"Skipped {job.job_number}."))
                return

            if replacement_number == "":
                self._clear_job(job, entry_count, dry_run=dry_run)
                return

            if replacement_number.lower() in {"new", "create", "c"}:
                self._complete_invalid_job(job, entry_count, dry_run=dry_run)
                return

            replacement = valid_replacement_jobs().filter(job_number__iexact=replacement_number).first()
            if replacement is None:
                self.stdout.write(self.style.ERROR("That replacement job number is not valid or not available for time entry."))
                continue

            if replacement.pk == job.pk:
                self.stdout.write(self.style.ERROR("Replacement job cannot be the same invalid job."))
                continue

            self._replace_job(job, replacement, entry_count, dry_run=dry_run)
            return

    def _complete_invalid_job(self, job, entry_count, dry_run=False):
        """Turn an invalid blank-description job into a real job record.

        This keeps the existing Job row, fills in required identifying data,
        and makes sure all matching TimeEntry rows point to this completed job.
        """
        old_number = job.job_number
        self.stdout.write("")
        self.stdout.write(f"Create/complete job record for invalid job {old_number}")

        new_number = input(f"Job number [{old_number}]: ").strip() or old_number
        description = input("Description: ").strip()
        while not description:
            self.stdout.write(self.style.ERROR("Description is required to make this a valid job."))
            description = input("Description: ").strip()

        customer_name = input("Customer name [blank for none]: ").strip()
        status = input(f"Job status [{Job.STATUS_UNKNOWN}]: ").strip() or Job.STATUS_UNKNOWN
        active_answer = input("Available for Time Entry? [y/N]: ").strip().lower()
        active = active_answer in {"y", "yes"}

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Would update invalid job {old_number} to job number {new_number}, "
                    f"description '{description}', status '{status}', active={active}; "
                    f"would keep/repoint {entry_count} time entries to this job."
                )
            )
            return

        try:
            with transaction.atomic():
                entries = entries_for_invalid_job(job)
                customer = None
                if customer_name:
                    customer, _ = Customer.objects.get_or_create(name=customer_name)

                job.job_number = new_number
                job.description = description
                job.customer = customer
                job.job_status = status
                job.active = active
                job.save()

                updated = entries.update(job=job, job_number=job.job_number)
        except IntegrityError:
            self.stdout.write(
                self.style.ERROR(
                    f"Could not create/complete job {new_number}. A job with that number may already exist. "
                    "Use that existing job number as the replacement instead."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Completed job {job.job_number} and assigned {updated} time entries to it. "
                "The job record was kept, not deleted."
            )
        )

    def _clear_job(self, job, entry_count, dry_run=False):
        if dry_run:
            self.stdout.write(self.style.WARNING(f"Would clear {entry_count} entries and delete invalid job {job.job_number}."))
            return
        with transaction.atomic():
            updated = cleanup_invalid_job(job, replacement_job=None)
        self.stdout.write(self.style.SUCCESS(f"Cleared {updated} entries and deleted invalid job {job.job_number}."))

    def _replace_job(self, job, replacement, entry_count, dry_run=False):
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Would reassign {entry_count} entries from {job.job_number} to {replacement.job_number} "
                    f"and delete invalid job {job.job_number}."
                )
            )
            return
        old_number = job.job_number
        with transaction.atomic():
            updated = cleanup_invalid_job(job, replacement_job=replacement)
        self.stdout.write(
            self.style.SUCCESS(
                f"Reassigned {updated} entries from {old_number} to {replacement.job_number} and deleted invalid job {old_number}."
            )
        )
