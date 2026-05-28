from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from timesheets.models import TimeEntry, WorkCode


class Command(BaseCommand):
    help = "Merge an invalid work code into a replacement work code."

    def add_arguments(self, parser):
        parser.add_argument("bad_code")
        parser.add_argument("replacement_code")

    @transaction.atomic
    def handle(self, *args, **options):
        bad_code = options["bad_code"]
        replacement_code = options["replacement_code"]

        if bad_code == replacement_code:
            raise CommandError("Bad code and replacement code cannot be the same.")

        try:
            bad = WorkCode.objects.get(code=bad_code)
        except WorkCode.DoesNotExist:
            raise CommandError(f"Bad work code not found: {bad_code}")

        try:
            replacement = WorkCode.objects.get(code=replacement_code)
        except WorkCode.DoesNotExist:
            raise CommandError(f"Replacement work code not found: {replacement_code}")

        updated = TimeEntry.objects.filter(work_code=bad).update(work_code=replacement)
        bad.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Merged work code {bad_code} into {replacement_code}. Updated {updated} time entries."
            )
        )
