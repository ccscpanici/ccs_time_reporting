import re

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from timesheets.models import Job


def normalize_name(value):
    """Normalize spreadsheet-style names for matching to Django users."""
    value = (value or "").strip()
    value = re.sub(r"\s+", " ", value)
    return value.casefold()


class Command(BaseCommand):
    help = "Link Job lead/engineer text fields to User foreign-key fields by FirstName LastName."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without saving anything.",
        )
        parser.add_argument(
            "--active-only",
            action="store_true",
            help="Only process active jobs.",
        )
        parser.add_argument(
            "--clear-missing",
            action="store_true",
            help="Clear linked user fields when the text name is blank or no matching user is found.",
        )

    def build_user_lookup(self):
        User = get_user_model()
        lookup = {}
        duplicates = set()

        for user in User.objects.all():
            full_name = f"{user.first_name or ''} {user.last_name or ''}"
            key = normalize_name(full_name)
            if not key:
                continue
            if key in lookup:
                duplicates.add(key)
            else:
                lookup[key] = user

        for key in duplicates:
            lookup.pop(key, None)

        return lookup, duplicates

    def find_user(self, lookup, name):
        key = normalize_name(name)
        if not key:
            return None
        return lookup.get(key)

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        active_only = options["active_only"]
        clear_missing = options["clear_missing"]

        user_lookup, duplicate_names = self.build_user_lookup()

        jobs = Job.objects.all().order_by("job_number")
        if active_only:
            jobs = jobs.filter(active=True)

        lead_linked = 0
        lead_cleared = 0
        engineer_linked = 0
        engineer_cleared = 0
        engineer_m2m_updated = 0
        missing_names = set()
        changed_jobs = 0

        engineer_slots = [f"engineer_{i:02d}" for i in range(1, 11)]

        with transaction.atomic():
            for job in jobs:
                changed_fields = []
                m2m_users = []

                # Lead text field -> lead_user foreign key.
                lead_name = getattr(job, "lead", "")
                lead_user = self.find_user(user_lookup, lead_name)
                current_lead_user_id = getattr(job, "lead_user_id", None)

                if lead_user and current_lead_user_id != lead_user.id:
                    job.lead_user = lead_user
                    changed_fields.append("lead_user")
                    lead_linked += 1
                elif not lead_user:
                    if normalize_name(lead_name):
                        missing_names.add(lead_name.strip())
                    if clear_missing and current_lead_user_id is not None:
                        job.lead_user = None
                        changed_fields.append("lead_user")
                        lead_cleared += 1

                # Engineer01-Engineer10 text fields -> matching FK fields and M2M list.
                for slot in engineer_slots:
                    engineer_name = getattr(job, slot, "")
                    engineer_user = self.find_user(user_lookup, engineer_name)
                    fk_field = f"{slot}_user"
                    fk_id_field = f"{slot}_user_id"

                    if engineer_user:
                        m2m_users.append(engineer_user)
                        if hasattr(job, fk_id_field) and getattr(job, fk_id_field) != engineer_user.id:
                            setattr(job, fk_field, engineer_user)
                            changed_fields.append(fk_field)
                            engineer_linked += 1
                    else:
                        if normalize_name(engineer_name):
                            missing_names.add(engineer_name.strip())
                        if clear_missing and hasattr(job, fk_id_field) and getattr(job, fk_id_field) is not None:
                            setattr(job, fk_field, None)
                            changed_fields.append(fk_field)
                            engineer_cleared += 1

                if changed_fields:
                    changed_jobs += 1
                    if not dry_run:
                        job.save(update_fields=sorted(set(changed_fields + ["updated_at"])))

                if hasattr(job, "engineer_users"):
                    desired_ids = sorted({user.id for user in m2m_users})
                    current_ids = sorted(job.engineer_users.values_list("id", flat=True))
                    if desired_ids != current_ids:
                        engineer_m2m_updated += 1
                        if not dry_run:
                            job.engineer_users.set(m2m_users)

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS("Job user linking complete."))
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: no database changes were saved."))
        self.stdout.write(f"Jobs scanned: {jobs.count()}")
        self.stdout.write(f"Jobs changed: {changed_jobs}")
        self.stdout.write(f"Lead links updated: {lead_linked}")
        self.stdout.write(f"Lead links cleared: {lead_cleared}")
        self.stdout.write(f"Engineer FK links updated: {engineer_linked}")
        self.stdout.write(f"Engineer FK links cleared: {engineer_cleared}")
        self.stdout.write(f"Engineer many-to-many rows updated: {engineer_m2m_updated}")

        if duplicate_names:
            self.stdout.write(self.style.WARNING("Duplicate user full names ignored:"))
            for name in sorted(duplicate_names):
                self.stdout.write(f"  - {name}")

        if missing_names:
            self.stdout.write(self.style.WARNING("Names not matched to users:"))
            for name in sorted(missing_names):
                self.stdout.write(f"  - {name}")
