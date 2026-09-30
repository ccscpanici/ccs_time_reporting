import re

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from timesheets.models import Job, JobUserAlias


def normalize_name(value):
    """Normalize spreadsheet-style names for matching."""
    value = (value or "").strip()
    value = re.sub(r"\s+", " ", value)
    return value.casefold()


def suggested_username(value):
    """
    Convert a simple FirstName LastName value to first-initial + last-name.

    Christopher Panici -> cpanici
    Fulton Wylie       -> fwylie

    Return an empty string when the value does not look like a simple
    person's name.
    """
    value = (value or "").strip()
    parts = value.split()

    if len(parts) < 2:
        return ""

    # Don't try to automatically interpret obvious compound/dirty values.
    if any(separator in value for separator in ("/", "|")):
        return ""

    first = re.sub(r"[^A-Za-z0-9]", "", parts[0])
    last = re.sub(r"[^A-Za-z0-9]", "", parts[-1])

    if not first or not last:
        return ""

    return (first[0] + last).casefold()


class Command(BaseCommand):
    help = (
        "Link Job lead/engineer text fields to Django users. "
        "Interactive mode can resolve unmatched names and remember aliases."
    )

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
            help=(
                "Clear linked user fields when the text name is blank or "
                "no matching user is found."
            ),
        )
        parser.add_argument(
            "--interactive",
            action="store_true",
            help="Prompt for unmatched names.",
        )

    def build_user_lookup(self):
        """
        Build lookup by normalized full name.

        Duplicate full names are intentionally excluded so an ambiguous
        name is never assigned automatically.
        """
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

    def build_username_lookup(self):
        User = get_user_model()
        lookup = {}
        duplicates = set()

        for user in User.objects.all():
            key = (user.username or "").strip().casefold()
            if not key:
                continue

            if key in lookup:
                duplicates.add(key)
            else:
                lookup[key] = user

        for key in duplicates:
            lookup.pop(key, None)

        return lookup

    def build_email_lookup(self):
        User = get_user_model()
        lookup = {}
        duplicates = set()

        for user in User.objects.all():
            key = (user.email or "").strip().casefold()
            if not key:
                continue

            if key in lookup:
                duplicates.add(key)
            else:
                lookup[key] = user

        for key in duplicates:
            lookup.pop(key, None)

        return lookup

    def build_alias_lookup(self):
        return {
            normalize_name(alias.source_name): alias.user
            for alias in JobUserAlias.objects.select_related("user").all()
            if normalize_name(alias.source_name)
        }

    def find_user_by_manual_entry(
        self,
        value,
        username_lookup,
        email_lookup,
        full_name_lookup,
    ):
        key = (value or "").strip().casefold()
        if not key:
            return None

        user = username_lookup.get(key)
        if user:
            return user

        user = email_lookup.get(key)
        if user:
            return user

        user = full_name_lookup.get(normalize_name(value))
        if user:
            return user

        # Convenience: allow cpanici even if the account is represented
        # primarily by cpanici@gotoccs.com, and vice versa.
        if "@" not in key:
            user = email_lookup.get(f"{key}@gotoccs.com")
            if user:
                return user

        return None

    def automatic_match(
        self,
        name,
        full_name_lookup,
        username_lookup,
        email_lookup,
        alias_lookup,
    ):
        """
        Resolution order:
          1. Persisted alias
          2. Exact normalized FirstName LastName
          3. first initial + last name as username
          4. first initial + last name + @gotoccs.com as email
        """
        normalized = normalize_name(name)
        if not normalized:
            return None, None

        user = alias_lookup.get(normalized)
        if user:
            return user, "alias"

        user = full_name_lookup.get(normalized)
        if user:
            return user, "full name"

        candidate = suggested_username(name)
        if candidate:
            user = username_lookup.get(candidate)
            if user:
                return user, f"username {candidate}"

            candidate_email = f"{candidate}@gotoccs.com"
            user = email_lookup.get(candidate_email)
            if user:
                return user, f"email {candidate_email}"

        return None, None

    def list_users(self):
        User = get_user_model()

        users = User.objects.all().order_by(
            "last_name",
            "first_name",
            "username",
        )

        self.stdout.write("")
        self.stdout.write(
            f"{'USERNAME':<24} {'NAME':<32} EMAIL"
        )
        self.stdout.write("-" * 90)

        for user in users:
            full_name = user.get_full_name().strip()
            self.stdout.write(
                f"{user.username:<24} "
                f"{full_name:<32} "
                f"{user.email or ''}"
            )

        self.stdout.write("")

    def prompt_for_user(
        self,
        *,
        job,
        field_label,
        source_name,
        username_lookup,
        email_lookup,
        full_name_lookup,
    ):
        while True:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("User match required"))
            self.stdout.write(f"Job:              {job.job_number}")
            self.stdout.write(f"Description:      {job.description or '-'}")
            self.stdout.write(f"Field:            {field_label}")
            self.stdout.write(f"Spreadsheet name: {source_name}")
            self.stdout.write("")
            self.stdout.write(
                "Enter username/email/full name, "
                "[L]ist users, [S]kip, [Q]uit"
            )

            try:
                answer = input("Selection: ").strip()
            except (EOFError, KeyboardInterrupt):
                self.stdout.write("")
                return "quit", None

            command = answer.casefold()

            if command == "l":
                self.list_users()
                continue

            if command == "s":
                return "skip", None

            if command == "q":
                return "quit", None

            user = self.find_user_by_manual_entry(
                answer,
                username_lookup,
                email_lookup,
                full_name_lookup,
            )

            if user:
                return "user", user

            self.stdout.write(
                self.style.ERROR(
                    f"No user found for '{answer}'. "
                    "Try again, [L]ist users, [S]kip, or [Q]uit."
                )
            )

    def save_alias(
        self,
        source_name,
        user,
        alias_lookup,
        *,
        dry_run,
    ):
        normalized = normalize_name(source_name)
        if not normalized:
            return False

        # Always remember it for the remainder of this process.
        alias_lookup[normalized] = user

        if dry_run:
            return False

        alias, created = JobUserAlias.objects.update_or_create(
            source_name__iexact=source_name.strip(),
            defaults={
                "source_name": source_name.strip(),
                "user": user,
            },
        )

        return created

    def resolve_user(
        self,
        *,
        job,
        field_label,
        source_name,
        full_name_lookup,
        username_lookup,
        email_lookup,
        alias_lookup,
        skipped_names,
        interactive,
        dry_run,
    ):
        normalized = normalize_name(source_name)

        if not normalized:
            return "missing", None, None

        if normalized in skipped_names:
            return "skipped", None, None

        user, method = self.automatic_match(
            source_name,
            full_name_lookup,
            username_lookup,
            email_lookup,
            alias_lookup,
        )

        if user:
            return "user", user, method

        if not interactive:
            return "missing", None, None

        action, user = self.prompt_for_user(
            job=job,
            field_label=field_label,
            source_name=source_name,
            username_lookup=username_lookup,
            email_lookup=email_lookup,
            full_name_lookup=full_name_lookup,
        )

        if action == "skip":
            skipped_names.add(normalized)
            return "skipped", None, None

        if action == "quit":
            return "quit", None, None

        self.save_alias(
            source_name,
            user,
            alias_lookup,
            dry_run=dry_run,
        )

        return "user", user, "manual"

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        active_only = options["active_only"]
        clear_missing = options["clear_missing"]
        interactive = options["interactive"]

        full_name_lookup, duplicate_names = self.build_user_lookup()
        username_lookup = self.build_username_lookup()
        email_lookup = self.build_email_lookup()
        alias_lookup = self.build_alias_lookup()

        # A skip applies to the normalized source name for the rest of
        # this run so values such as TBD or ?? only prompt once.
        skipped_names = set()

        jobs = Job.objects.all().order_by("job_number")
        if active_only:
            jobs = jobs.filter(active=True)

        jobs_count = jobs.count()

        lead_linked = 0
        lead_cleared = 0
        engineer_linked = 0
        engineer_cleared = 0
        engineer_m2m_updated = 0
        missing_names = set()
        changed_jobs = 0
        manual_matches = 0
        automatic_matches = 0

        engineer_slots = [
            f"engineer_{i:02d}"
            for i in range(1, 11)
        ]

        quit_requested = False

        with transaction.atomic():
            for job in jobs:
                changed_fields = []

                # Start with currently linked engineer users. This is
                # important: this command fills missing links and does not
                # discard existing manual engineer assignments.
                existing_engineer_users = []
                if hasattr(job, "engineer_users"):
                    existing_engineer_users = list(job.engineer_users.all())

                m2m_users = list(existing_engineer_users)

                # Lead text field -> lead_user.
                lead_name = getattr(job, "lead", "")
                current_lead_user_id = getattr(job, "lead_user_id", None)

                if normalize_name(lead_name) and current_lead_user_id is None:
                    action, lead_user, method = self.resolve_user(
                        job=job,
                        field_label="Lead",
                        source_name=lead_name,
                        full_name_lookup=full_name_lookup,
                        username_lookup=username_lookup,
                        email_lookup=email_lookup,
                        alias_lookup=alias_lookup,
                        skipped_names=skipped_names,
                        interactive=interactive,
                        dry_run=dry_run,
                    )

                    if action == "quit":
                        quit_requested = True
                    elif lead_user:
                        job.lead_user = lead_user
                        changed_fields.append("lead_user")
                        lead_linked += 1

                        if method == "manual":
                            manual_matches += 1
                        else:
                            automatic_matches += 1
                    elif action == "missing":
                        missing_names.add(lead_name.strip())

                elif (
                    clear_missing
                    and not normalize_name(lead_name)
                    and current_lead_user_id is not None
                ):
                    job.lead_user = None
                    changed_fields.append("lead_user")
                    lead_cleared += 1

                if quit_requested:
                    if changed_fields and not dry_run:
                        job.save(
                            update_fields=sorted(
                                set(changed_fields + ["updated_at"])
                            )
                        )
                    break

                # Engineer text fields -> matching FK fields and M2M.
                for slot in engineer_slots:
                    engineer_name = getattr(job, slot, "")
                    fk_field = f"{slot}_user"
                    fk_id_field = f"{slot}_user_id"

                    current_engineer_user_id = (
                        getattr(job, fk_id_field)
                        if hasattr(job, fk_id_field)
                        else None
                    )

                    engineer_user = None

                    if (
                        normalize_name(engineer_name)
                        and current_engineer_user_id is None
                    ):
                        action, engineer_user, method = self.resolve_user(
                            job=job,
                            field_label=slot.replace("_", " ").title(),
                            source_name=engineer_name,
                            full_name_lookup=full_name_lookup,
                            username_lookup=username_lookup,
                            email_lookup=email_lookup,
                            alias_lookup=alias_lookup,
                            skipped_names=skipped_names,
                            interactive=interactive,
                            dry_run=dry_run,
                        )

                        if action == "quit":
                            quit_requested = True
                            break

                        if engineer_user:
                            if hasattr(job, fk_id_field):
                                setattr(job, fk_field, engineer_user)
                                changed_fields.append(fk_field)
                                engineer_linked += 1

                            m2m_users.append(engineer_user)

                            if method == "manual":
                                manual_matches += 1
                            else:
                                automatic_matches += 1

                        elif action == "missing":
                            missing_names.add(engineer_name.strip())

                    elif (
                        clear_missing
                        and not normalize_name(engineer_name)
                        and current_engineer_user_id is not None
                    ):
                        setattr(job, fk_field, None)
                        changed_fields.append(fk_field)
                        engineer_cleared += 1

                        # Remove the stale user from the M2M collection too.
                        m2m_users = [
                            user
                            for user in m2m_users
                            if user.id != current_engineer_user_id
                        ]

                    elif current_engineer_user_id is not None:
                        if hasattr(job, fk_field):
                            engineer_user = getattr(job, fk_field)
                            if engineer_user:
                                m2m_users.append(engineer_user)

                if changed_fields:
                    changed_jobs += 1
                    if not dry_run:
                        job.save(
                            update_fields=sorted(
                                set(changed_fields + ["updated_at"])
                            )
                        )

                if hasattr(job, "engineer_users"):
                    unique_users = {
                        user.id: user
                        for user in m2m_users
                        if user is not None
                    }
                    desired_ids = sorted(unique_users)
                    current_ids = sorted(
                        job.engineer_users.values_list("id", flat=True)
                    )

                    if desired_ids != current_ids:
                        engineer_m2m_updated += 1
                        if not dry_run:
                            job.engineer_users.set(unique_users.values())

                if quit_requested:
                    break

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS("Job user linking complete.")
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN: no database changes or aliases were saved."
                )
            )

        if quit_requested:
            self.stdout.write(
                self.style.WARNING(
                    "Stopped early at user request. "
                    "Changes completed before quitting were preserved."
                )
            )

        self.stdout.write(f"Jobs available to scan: {jobs_count}")
        self.stdout.write(f"Jobs changed: {changed_jobs}")
        self.stdout.write(f"Lead links updated: {lead_linked}")
        self.stdout.write(f"Lead links cleared: {lead_cleared}")
        self.stdout.write(
            f"Engineer FK links updated: {engineer_linked}"
        )
        self.stdout.write(
            f"Engineer FK links cleared: {engineer_cleared}"
        )
        self.stdout.write(
            "Engineer many-to-many rows updated: "
            f"{engineer_m2m_updated}"
        )
        self.stdout.write(f"Automatic matches: {automatic_matches}")
        self.stdout.write(f"Manual matches: {manual_matches}")
        self.stdout.write(
            f"Names skipped this run: {len(skipped_names)}"
        )

        if duplicate_names:
            self.stdout.write(
                self.style.WARNING(
                    "Duplicate user full names ignored:"
                )
            )
            for name in sorted(duplicate_names):
                self.stdout.write(f"  - {name}")

        if missing_names:
            self.stdout.write(
                self.style.WARNING("Names not matched to users:")
            )
            for name in sorted(missing_names):
                self.stdout.write(f"  - {name}")
