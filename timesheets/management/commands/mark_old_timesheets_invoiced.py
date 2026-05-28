from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from timesheets.models import Timesheet


class Command(BaseCommand):
    help = "Mark approved timesheets older than X days as invoiced."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=14,
            help="Age in days before approved timesheets are marked invoiced.",
        )

        parser.add_argument(
            "--username",
            type=str,
            default="cpanici",
            help="Username to record as invoiced_by.",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without making changes.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        username = options["username"]
        dry_run = options["dry_run"]

        cutoff = timezone.localdate() - timedelta(days=days)

        User = get_user_model()

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stderr.write(
                self.style.ERROR(f"User not found: {username}")
            )
            return

        qs = Timesheet.objects.filter(
            status=Timesheet.Status.APPROVED,
            week_start__lt=cutoff,
            deleted_at__isnull=True,
        )

        count = qs.count()

        self.stdout.write(
            f"Found {count} approved timesheets older than {days} days."
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING("Dry run enabled. No changes made.")
            )
            return

        updated = qs.update(
            status=Timesheet.Status.INVOICED,
            invoiced_at=timezone.now(),
            invoiced_by=user,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Marked {updated} timesheets as invoiced."
            )
        )
