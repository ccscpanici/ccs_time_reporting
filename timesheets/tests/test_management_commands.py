from __future__ import annotations

from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
import zipfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone

from timesheets.management.commands.import_jobs import (
    clean_date,
    clean_job_number,
    clean_text,
    clean_year,
    is_year_separator_row,
    resolve_user_by_full_name,
    user_full_name_key,
)
from timesheets.management.commands.invalid_jobs import Command as InvalidJobsCommand
from timesheets.management.commands.link_job_users import Command as LinkJobUsersCommand, normalize_name
from timesheets.models import Customer, Job, TimeEntry, Timesheet, TimesheetImport, WorkCode
from timesheets.tests.base import AppTestCase
from timesheets.tests.factories import make_job, make_time_entry, make_timesheet, make_user, write_job_workbook


class ImportJobsCommandTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base = Path(self.temp_dir.name)

    def workbook(self, *, headers=None, rows=None, sheet_title="Jobs - Quotes"):
        headers = headers or [
            "Quote/Job #", "Year", "Customer", "Job Status", "Description",
            "Lead", "Engineer01", "Quote Date", "Accepted Date",
        ]
        return write_job_workbook(
            self.base / "jobs.xlsx",
            headers=headers,
            rows=rows or [],
            sheet_title=sheet_title,
            preface_rows=[["CCS Job List"]],
        )

    def test_cleaning_helpers(self):
        self.assertEqual(clean_text(12.0), "12")
        self.assertEqual(clean_text("  abc  "), "abc")
        self.assertEqual(clean_job_number(26001.0), "26001")
        self.assertEqual(clean_year("26"), 2026)
        self.assertEqual(clean_year("bad"), None)
        self.assertEqual(clean_date("08/06/2026"), date(2026, 8, 6))
        self.assertIsNone(clean_date("bad"))

    def test_user_name_helpers(self):
        user = make_user(username="cpanici", first_name="Chris", last_name="Panici")
        key = user_full_name_key(user)
        self.assertEqual(key, "chris panici")
        self.assertEqual(resolve_user_by_full_name(" Chris Panici ", {key: user}), user)
        self.assertIsNone(resolve_user_by_full_name("", {key: user}))

    def test_year_separator_detection(self):
        self.assertTrue(is_year_separator_row("2026", {}, ""))
        self.assertFalse(is_year_separator_row("2026", {"description": "Real job"}, ""))
        self.assertFalse(is_year_separator_row("26001", {}, ""))

    def test_missing_workbook_raises_command_error(self):
        with self.assertRaisesMessage(CommandError, "Workbook not found"):
            call_command("import_jobs", str(self.base / "missing.xlsx"))

    def test_missing_sheet_raises_command_error(self):
        path = self.workbook(sheet_title="Other")
        with self.assertRaisesMessage(CommandError, "was not found"):
            call_command("import_jobs", str(path))

    def test_missing_job_number_header_raises_command_error(self):
        path = self.workbook(headers=["Description"], rows=[["No number"]])
        with self.assertRaisesMessage(CommandError, "Quote/Job #"):
            call_command("import_jobs", str(path))

    def test_apply_import_creates_jobs_customer_and_user_links(self):
        lead = make_user(username="lead", first_name="Chris", last_name="Panici")
        engineer = make_user(username="eng", first_name="Jane", last_name="Engineer")
        path = self.workbook(rows=[[
            "26001", "", "Acme", "", "Controls upgrade",
            "Chris Panici", "Jane Engineer", "08/01/2026", "08/02/2026",
        ]])
        out = StringIO()

        call_command("import_jobs", str(path), stdout=out)

        job = Job.objects.get(job_number="26001")
        self.assertEqual(job.customer.name, "Acme")
        self.assertEqual(job.lead_user, lead)
        self.assertEqual(job.engineer_01_user, engineer)
        self.assertEqual(job.job_status, Job.STATUS_UNKNOWN)
        self.assertEqual(job.year, 2026)
        self.assertIn("created=1", out.getvalue())
        self.assertIn("blank_status_as_unknown=1", out.getvalue())

    def test_import_updates_existing_and_skips_blank_and_year_rows(self):
        make_job(job_number="26001", description="Old")
        path = self.workbook(rows=[
            ["", "", "", "", "", "", "", "", ""],
            ["2026", "", "", "", "", "", "", "", ""],
            ["26001", "2026", "", Job.STATUS_ACTIVE, "Updated", "", "", "", ""],
        ])
        out = StringIO()

        call_command("import_jobs", str(path), stdout=out)

        self.assertEqual(Job.objects.get(job_number="26001").description, "Updated")
        self.assertIn("updated=1", out.getvalue())
        self.assertIn("skipped=2", out.getvalue())

    def test_dry_run_reports_but_rolls_back_database_changes(self):
        path = self.workbook(rows=[["26099", "2026", "Acme", "Active", "Dry run", "", "", "", ""]])
        out = StringIO()

        call_command("import_jobs", str(path), dry_run=True, stdout=out)

        self.assertFalse(Job.objects.filter(job_number="26099").exists())
        self.assertFalse(Customer.objects.filter(name="Acme").exists())
        self.assertIn("DRY RUN", out.getvalue())


class MergeWorkCodeCommandTests(AppTestCase):
    def test_merge_updates_entries_and_deletes_bad_code(self):
        user = make_user(username="worker")
        ts = make_timesheet(employee=user, week_start=date(2026, 8, 2))
        bad = WorkCode.objects.create(code="BAD", description="Bad")
        replacement = WorkCode.objects.create(code="GOOD", description="Good")
        entry = make_time_entry(timesheet=ts, work_code=bad)
        out = StringIO()

        call_command("merge_work_code", "BAD", "GOOD", stdout=out)

        entry.refresh_from_db()
        self.assertEqual(entry.work_code, replacement)
        self.assertFalse(WorkCode.objects.filter(code="BAD").exists())
        self.assertIn("Updated 1 time entries", out.getvalue())

    def test_same_or_missing_codes_raise_command_errors(self):
        WorkCode.objects.create(code="GOOD", description="Good")
        with self.assertRaisesMessage(CommandError, "cannot be the same"):
            call_command("merge_work_code", "GOOD", "GOOD")
        with self.assertRaisesMessage(CommandError, "Bad work code not found"):
            call_command("merge_work_code", "BAD", "GOOD")
        WorkCode.objects.create(code="BAD", description="Bad")
        with self.assertRaisesMessage(CommandError, "Replacement work code not found"):
            call_command("merge_work_code", "BAD", "NOPE")


class MarkOldTimesheetsInvoicedCommandTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.actor = make_user(username="cpanici")
        self.employee = make_user(username="employee")

    def test_marks_only_old_approved_non_deleted_timesheets(self):
        today = timezone.localdate()
        old = make_timesheet(employee=self.employee, week_start=today - timedelta(days=30), status=Timesheet.Status.APPROVED)
        recent = make_timesheet(employee=self.employee, week_start=today - timedelta(days=7), status=Timesheet.Status.APPROVED)
        deleted = make_timesheet(employee=make_user(username="deleted"), week_start=today - timedelta(days=30), status=Timesheet.Status.APPROVED, deleted_at=timezone.now())
        out = StringIO()

        call_command("mark_old_timesheets_invoiced", days=14, username="cpanici", stdout=out)

        old.refresh_from_db(); recent.refresh_from_db(); deleted.refresh_from_db()
        self.assertEqual(old.status, Timesheet.Status.INVOICED)
        self.assertEqual(old.invoiced_by, self.actor)
        self.assertEqual(recent.status, Timesheet.Status.APPROVED)
        self.assertEqual(deleted.status, Timesheet.Status.APPROVED)
        self.assertIn("Marked 1 timesheets", out.getvalue())

    def test_dry_run_and_missing_user_make_no_changes(self):
        old = make_timesheet(employee=self.employee, week_start=timezone.localdate() - timedelta(days=30), status=Timesheet.Status.APPROVED)
        out = StringIO()
        call_command("mark_old_timesheets_invoiced", days=14, username="cpanici", dry_run=True, stdout=out)
        old.refresh_from_db()
        self.assertEqual(old.status, Timesheet.Status.APPROVED)
        self.assertIn("No changes made", out.getvalue())

        err = StringIO()
        call_command("mark_old_timesheets_invoiced", username="missing", stderr=err)
        self.assertIn("User not found", err.getvalue())


class LinkJobUsersCommandTests(AppTestCase):
    def test_normalize_and_duplicate_lookup_behavior(self):
        self.assertEqual(normalize_name("  Chris   Panici "), "chris panici")
        make_user(username="one", first_name="Same", last_name="Name")
        make_user(username="two", first_name="Same", last_name="Name")
        lookup, duplicates = LinkJobUsersCommand().build_user_lookup()
        self.assertIn("same name", duplicates)
        self.assertNotIn("same name", lookup)

    def test_links_lead_engineer_fks_and_many_to_many(self):
        lead = make_user(username="lead", first_name="Lead", last_name="Person")
        engineer = make_user(username="eng", first_name="Engineer", last_name="Person")
        job = make_job(job_number="26001", lead="Lead Person", engineer_01="Engineer Person")
        out = StringIO()

        call_command("link_job_users", stdout=out)

        job.refresh_from_db()
        self.assertEqual(job.lead_user, lead)
        self.assertEqual(job.engineer_01_user, engineer)
        self.assertEqual(list(job.engineer_users.all()), [engineer])
        self.assertIn("Jobs changed: 1", out.getvalue())

    def test_active_only_dry_run_and_missing_name_reporting(self):
        user = make_user(username="person", first_name="Known", last_name="Person")
        active = make_job(job_number="26001", lead="Known Person")
        inactive = make_job(job_number="25001", active=False, lead="Known Person")
        missing = make_job(job_number="26002", lead="Missing Person")
        out = StringIO()

        call_command("link_job_users", active_only=True, dry_run=True, stdout=out)

        active.refresh_from_db(); inactive.refresh_from_db(); missing.refresh_from_db()
        self.assertIsNone(active.lead_user)
        self.assertIsNone(inactive.lead_user)
        self.assertIsNone(missing.lead_user)
        self.assertIn("DRY RUN", out.getvalue())
        self.assertIn("Missing Person", out.getvalue())

    def test_clear_missing_removes_stale_links_and_m2m(self):
        stale = make_user(username="stale", first_name="Stale", last_name="User")
        job = make_job(job_number="26001", lead="", lead_user=stale, engineer_01="", engineer_01_user=stale)
        job.engineer_users.add(stale)

        call_command("link_job_users", clear_missing=True)

        job.refresh_from_db()
        self.assertIsNone(job.lead_user)
        self.assertIsNone(job.engineer_01_user)
        self.assertEqual(job.engineer_users.count(), 0)


class ImportTimesheetZipCommandTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base = Path(self.temp_dir.name)
        self.user = make_user(username="employee")

    def make_zip(self, names=("one.xlsx", "nested/two.xlsx", "ignore.txt")):
        path = self.base / "timesheets.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for name in names:
                archive.writestr(name, b"dummy")
        return path

    def test_missing_zip_and_user_raise_command_errors(self):
        with self.assertRaisesMessage(CommandError, "ZIP file does not exist"):
            call_command("import_timesheet_zip", str(self.base / "missing.zip"), user="employee")
        path = self.make_zip()
        with self.assertRaisesMessage(CommandError, "User not found"):
            call_command("import_timesheet_zip", str(path), user="missing")

    @override_settings(DEFAULT_FILE_STORAGE="django.core.files.storage.FileSystemStorage")
    def test_imports_xlsx_members_and_applies_requested_status(self):
        path = self.make_zip()
        ts = make_timesheet(employee=self.user, week_start=date(2026, 8, 2))
        out = StringIO()
        with override_settings(MEDIA_ROOT=self.base / "media"), \
             patch("timesheets.management.commands.import_timesheet_zip.import_timesheet_upload", return_value=ts) as importer, \
             patch("timesheets.management.commands.import_timesheet_zip._apply_bulk_import_status") as apply_status:
            call_command("import_timesheet_zip", str(path), user="employee", submitted=True, approved=True, stdout=out)

        self.assertEqual(importer.call_count, 2)
        self.assertEqual(apply_status.call_count, 2)
        self.assertTrue(all(call.kwargs["mark_submitted"] for call in apply_status.call_args_list))
        self.assertTrue(all(call.kwargs["mark_approved"] for call in apply_status.call_args_list))
        self.assertIn("Found 2 XLSX files", out.getvalue())
        self.assertIn("Imported=2 Failed=0", out.getvalue())

    def test_failed_member_does_not_stop_remaining_imports(self):
        path = self.make_zip(names=("one.xlsx", "two.xlsx"))
        ts = make_timesheet(employee=self.user, week_start=date(2026, 8, 2))
        out = StringIO()
        with override_settings(MEDIA_ROOT=self.base / "media"), \
             patch("timesheets.management.commands.import_timesheet_zip.import_timesheet_upload", side_effect=[ValueError("bad file"), ts]), \
             patch("timesheets.management.commands.import_timesheet_zip._apply_bulk_import_status"):
            call_command("import_timesheet_zip", str(path), user="employee", stdout=out)

        self.assertIn("FAILED: one.xlsx", out.getvalue())
        self.assertIn("Imported=1 Failed=1", out.getvalue())


class InvalidJobsCommandTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user(username="employee")
        self.timesheet = make_timesheet(employee=self.user, week_start=date(2026, 8, 2))

    def test_no_invalid_jobs_and_limit_output(self):
        out = StringIO()
        call_command("invalid_jobs", stdout=out)
        self.assertIn("No invalid jobs found", out.getvalue())

        make_job(job_number="BAD1", description="")
        make_job(job_number="BAD2", description="")
        out = StringIO()
        with patch("builtins.input", side_effect=["skip"]):
            call_command("invalid_jobs", limit=1, stdout=out)
        self.assertIn("Found 1 invalid job", out.getvalue())

    def test_clear_and_replace_actions(self):
        invalid = make_job(job_number="BAD1", description="")
        replacement = make_job(job_number="26001", description="Valid")
        entry = make_time_entry(timesheet=self.timesheet, job=invalid, job_number="BAD1")
        command = InvalidJobsCommand()
        command.stdout = StringIO()

        command._replace_job(invalid, replacement, 1)

        entry.refresh_from_db()
        self.assertEqual(entry.job, replacement)
        self.assertFalse(Job.objects.filter(pk=invalid.pk).exists())

        invalid2 = make_job(job_number="BAD2", description="")
        entry2 = make_time_entry(timesheet=self.timesheet, row_order=2, job=invalid2, job_number="BAD2")
        command._clear_job(invalid2, 1)
        entry2.refresh_from_db()
        self.assertIsNone(entry2.job)
        self.assertEqual(entry2.job_number, "")

    def test_dry_run_actions_do_not_change_database(self):
        invalid = make_job(job_number="BAD1", description="")
        replacement = make_job(job_number="26001", description="Valid")
        entry = make_time_entry(timesheet=self.timesheet, job=invalid, job_number="BAD1")
        command = InvalidJobsCommand(); command.stdout = StringIO()

        command._replace_job(invalid, replacement, 1, dry_run=True)
        entry.refresh_from_db()
        self.assertEqual(entry.job, invalid)
        self.assertTrue(Job.objects.filter(pk=invalid.pk).exists())

    def test_complete_invalid_job_updates_record_and_entries(self):
        invalid = make_job(job_number="BAD1", description="")
        entry = make_time_entry(timesheet=self.timesheet, job=invalid, job_number="BAD1")
        command = InvalidJobsCommand(); command.stdout = StringIO()
        responses = ["26055", "Completed job", "Acme", Job.STATUS_ACTIVE, "y"]

        with patch("builtins.input", side_effect=responses):
            command._complete_invalid_job(invalid, 1)

        invalid.refresh_from_db(); entry.refresh_from_db()
        self.assertEqual(invalid.job_number, "26055")
        self.assertEqual(invalid.description, "Completed job")
        self.assertEqual(invalid.customer.name, "Acme")
        self.assertTrue(invalid.active)
        self.assertEqual(entry.job_number, "26055")

    def test_quit_raises_command_error(self):
        invalid = make_job(job_number="BAD1", description="")
        command = InvalidJobsCommand(); command.stdout = StringIO()
        with patch("builtins.input", return_value="quit"):
            with self.assertRaisesMessage(CommandError, "Stopped by user"):
                command._process_job(invalid)


class SeedWorkcodesCommandTests(AppTestCase):
    def test_command_calls_all_seeders_and_prints_completion(self):
        out = StringIO()
        targets = [
            "seed_work_codes", "seed_mileage_rates", "seed_overnight_rates",
            "seed_office_locations", "seed_management_group", "seed_project_managers_group",
        ]
        patches = [patch(f"timesheets.management.commands.seed_workcodes.{name}") for name in targets]
        mocks = [p.start() for p in patches]
        for p in patches:
            self.addCleanup(p.stop)

        call_command("seed_workcodes", stdout=out)

        for mocked in mocks:
            mocked.assert_called_once()
        self.assertIn("Default data seed complete", out.getvalue())
