from datetime import date, datetime, timezone as dt_timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from openpyxl import Workbook

from timesheets.models import Customer, Job
from timesheets.services.job_importer import (
    JobImportResult,
    _date,
    _int,
    _norm,
    _text,
    _user_map,
    apply_job_import,
    build_header_map,
    find_header_row,
    import_job_list,
    is_year_separator,
    preview_job_import,
)
from timesheets.tests.base import AppTestCase
from timesheets.tests.factories import write_job_workbook


class JobImporterHelperTests(AppTestCase):
    def test_norm_trims_collapses_and_lowercases(self):
        self.assertEqual(_norm("  Job   Number "), "job number")
        self.assertEqual(_norm(None), "")

    def test_text_handles_none_integer_float_and_strings(self):
        self.assertEqual(_text(None), "")
        self.assertEqual(_text(26001.0), "26001")
        self.assertEqual(_text(26001.5), "26001.5")
        self.assertEqual(_text("  ABC  "), "ABC")

    def test_date_parses_supported_values(self):
        expected = date(2026, 8, 6)
        self.assertEqual(_date(expected), expected)
        self.assertEqual(_date(datetime(2026, 8, 6, 10, 30)), expected)
        self.assertEqual(_date("08/06/2026"), expected)
        self.assertEqual(_date("08/06/26"), expected)
        self.assertEqual(_date("2026-08-06"), expected)

    def test_date_returns_none_for_blank_na_and_invalid(self):
        for value in (None, "", "N/A", "not-a-date"):
            with self.subTest(value=value):
                self.assertIsNone(_date(value))

    def test_int_parses_numeric_values_and_rejects_invalid(self):
        self.assertEqual(_int("2026"), 2026)
        self.assertEqual(_int(2026.0), 2026)
        self.assertEqual(_int("2026.9"), 2026)
        self.assertIsNone(_int(""))
        self.assertIsNone(_int("bad"))

    def test_user_map_contains_full_name_and_username(self):
        user = self.make_user(username="cpanici", first_name="Chris", last_name="Panici")
        mapping = _user_map()
        self.assertEqual(mapping["chris panici"], user)
        self.assertEqual(mapping["cpanici"], user)

    def test_header_detection_and_alias_mapping(self):
        wb = Workbook()
        ws = wb.active
        ws.append(["CCS Jobs"])
        ws.append(["Quote/Job #", "Customer", "Engineer 1", "Notes"])
        header_row = find_header_row(ws)
        header_map = build_header_map(ws, header_row)
        self.assertEqual(header_row, 2)
        self.assertEqual(header_map["job_number"], 1)
        self.assertEqual(header_map["customer"], 2)
        self.assertEqual(header_map["engineer_01"], 3)
        self.assertEqual(header_map["comments"], 4)

    def test_find_header_row_defaults_to_first_row(self):
        wb = Workbook()
        ws = wb.active
        ws.append(["No useful headings"])
        self.assertEqual(find_header_row(ws), 1)

    def test_year_separator_detection(self):
        self.assertTrue(is_year_separator([2026, None], 2026))
        self.assertTrue(is_year_separator(["2026", "Jobs"], "2026"))
        self.assertFalse(is_year_separator(["2026", "A", "B"], "2026"))
        self.assertFalse(is_year_separator(["26001"], "26001"))

    def test_result_total_changed(self):
        result = JobImportResult(added=2, updated=3, unchanged=4)
        self.assertEqual(result.total_changed, 5)


class JobImporterWorkbookTests(AppTestCase):
    headers = [
        "Quote/Job #", "Year", "Job Type", "CFR Job#", "Customer",
        "Job Status", "Invoice Status", "Work Type", "Location",
        "Customer Contact", "PO#", "Description", "Lead", "Quote Date",
        "Accepted Date", "Quote #", "Comments", "Engineer1", "Engineer 2",
    ]

    @classmethod
    def setUpTestData(cls):
        cls.lead = cls.make_user(username="leaduser", first_name="Chris", last_name="Lead")
        cls.engineer1 = cls.make_user(username="engineer1", first_name="Alice", last_name="Engineer")
        cls.engineer2 = cls.make_user(username="engineer2", first_name="Bob", last_name="Builder")

    def workbook(self, directory, rows, **kwargs):
        return write_job_workbook(
            Path(directory) / "jobs.xlsx",
            headers=kwargs.pop("headers", self.headers),
            rows=rows,
            **kwargs,
        )

    def full_row(self, **overrides):
        values = {
            "job_number": "26001", "year": 2026, "job_type": "Project",
            "cfr": "CFR-1", "customer": "Acme Foods", "status": Job.STATUS_ACTIVE,
            "invoice": Job.INVOICE_STATUS_PROGRESS, "work_type": "Controls",
            "location": "Waupun", "contact": "Pat Person", "po": "PO-123",
            "description": "Packaging line", "lead": "Chris Lead",
            "quote_date": "08/01/2026", "accepted_date": "2026-08-03",
            "quote_number": "Q-100", "comments": "Priority project",
            "engineer1": "Alice Engineer", "engineer2": "engineer2",
        }
        values.update(overrides)
        return [
            values["job_number"], values["year"], values["job_type"], values["cfr"],
            values["customer"], values["status"], values["invoice"], values["work_type"],
            values["location"], values["contact"], values["po"], values["description"],
            values["lead"], values["quote_date"], values["accepted_date"],
            values["quote_number"], values["comments"], values["engineer1"], values["engineer2"],
        ]

    def test_preview_reports_add_without_writing_database(self):
        with TemporaryDirectory() as directory:
            path = self.workbook(directory, [self.full_row()])
            result = preview_job_import(path)
        self.assertEqual(result.added, 1)
        self.assertEqual(Job.objects.count(), 0)
        self.assertEqual(Customer.objects.count(), 0)

    def test_apply_creates_full_job_customer_and_user_links(self):
        with TemporaryDirectory() as directory:
            path = self.workbook(directory, [self.full_row()])
            result = apply_job_import(path, user=self.lead, source_name="master.xlsx")
        self.assertEqual(result.added, 1)
        job = Job.objects.get(job_number="26001")
        self.assertEqual(job.customer.name, "Acme Foods")
        self.assertEqual(job.description, "Packaging line")
        self.assertEqual(job.year, 2026)
        self.assertEqual(job.job_type, "Project")
        self.assertEqual(job.cfr_job_number, "CFR-1")
        self.assertEqual(job.job_status, Job.STATUS_ACTIVE)
        self.assertEqual(job.invoice_status, Job.INVOICE_STATUS_PROGRESS)
        self.assertEqual(job.work_type, "Controls")
        self.assertEqual(job.location, "Waupun")
        self.assertEqual(job.customer_contact, "Pat Person")
        self.assertEqual(job.customer_po, "PO-123")
        self.assertEqual(job.lead, "Chris Lead")
        self.assertEqual(job.lead_user, self.lead)
        self.assertEqual(job.quote_date, date(2026, 8, 1))
        self.assertEqual(job.accepted_date, date(2026, 8, 3))
        self.assertEqual(job.quote_number, "Q-100")
        self.assertEqual(job.comments, "Priority project")
        self.assertEqual(job.import_source, "master.xlsx")
        self.assertIsNotNone(job.last_imported_at)
        self.assertEqual(set(job.engineer_users.all()), {self.engineer1, self.engineer2})

    def test_apply_reuses_existing_customer(self):
        customer = self.make_customer(name="Acme Foods")
        with TemporaryDirectory() as directory:
            result = apply_job_import(self.workbook(directory, [self.full_row()]))
        self.assertEqual(result.added, 1)
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Job.objects.get().customer, customer)

    def test_missing_job_number_header_returns_error(self):
        with TemporaryDirectory() as directory:
            path = self.workbook(directory, [["Acme", "Description"]], headers=["Customer", "Description"])
            result = preview_job_import(path)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("Could not find a Job Number column", result.errors[0])

    def test_preface_rows_and_active_sheet_fallback_are_supported(self):
        with TemporaryDirectory() as directory:
            path = self.workbook(directory, [self.full_row()], sheet_title="Other", preface_rows=[["CCS Job Master"], []])
            result = preview_job_import(path)
        self.assertEqual(result.added, 1)

    def test_blank_year_separator_and_invalid_rows_are_counted(self):
        rows = [
            [None] * len(self.headers),
            [2026, None] + [None] * (len(self.headers) - 2),
            ["NOJOB"] + [None] * (len(self.headers) - 1),
            self.full_row(),
        ]
        with TemporaryDirectory() as directory:
            result = preview_job_import(self.workbook(directory, rows))
        self.assertEqual(result.ignored_blank, 1)
        self.assertEqual(result.ignored_year_rows, 1)
        self.assertEqual(result.ignored_invalid, 1)
        self.assertEqual(result.added, 1)

    def test_unknown_lead_and_engineers_are_reported(self):
        row = self.full_row(lead="Missing Lead", engineer1="Missing Engineer", engineer2="")
        with TemporaryDirectory() as directory:
            result = preview_job_import(self.workbook(directory, [row]))
        self.assertEqual(result.unknown_leads, {"Missing Lead"})
        self.assertEqual(result.unknown_engineers, {"Missing Engineer"})

    def test_blank_status_defaults_to_unknown(self):
        with TemporaryDirectory() as directory:
            apply_job_import(self.workbook(directory, [self.full_row(status="")]))
        self.assertEqual(Job.objects.get().job_status, Job.STATUS_UNKNOWN)

    def test_existing_job_is_marked_unchanged_when_values_match(self):
        fixed_now = datetime(2026, 8, 6, 12, 0, tzinfo=dt_timezone.utc)
        customer = self.make_customer(name="Acme Foods")
        job = self.make_job_record(
            job_number="26001", customer=customer, description="Packaging line", year=2026,
            job_type="Project", cfr_job_number="CFR-1", job_status=Job.STATUS_ACTIVE,
            invoice_status=Job.INVOICE_STATUS_PROGRESS, work_type="Controls", location="Waupun",
            customer_contact="Pat Person", customer_po="PO-123", lead="Chris Lead",
            lead_user=self.lead, quote_date=date(2026, 8, 1), accepted_date=date(2026, 8, 3),
            quote_number="Q-100", comments="Priority project", import_source="master.xlsx",
            last_imported_at=fixed_now, engineer_01="Alice Engineer", engineer_02="engineer2",
        )
        job.engineer_users.set([self.engineer1, self.engineer2])
        with TemporaryDirectory() as directory, patch(
            "timesheets.services.job_importer.timezone.now", return_value=fixed_now
        ):
            result = import_job_list(
                self.workbook(directory, [self.full_row()]),
                apply=False,
                source_name="master.xlsx",
            )
        self.assertEqual(result.unchanged, 1)
        self.assertEqual(result.updated, 0)

    def test_existing_job_updates_changed_fields_and_engineers(self):
        customer = self.make_customer(name="Old Customer")
        job = self.make_job_record(job_number="26001", customer=customer, description="Old", lead_user=None)
        job.engineer_users.set([self.engineer1])
        with TemporaryDirectory() as directory:
            result = apply_job_import(self.workbook(directory, [self.full_row()]), source_name="new.xlsx")
        job.refresh_from_db()
        self.assertEqual(result.updated, 1)
        self.assertEqual(job.description, "Packaging line")
        self.assertEqual(job.customer.name, "Acme Foods")
        self.assertEqual(job.lead_user, self.lead)
        self.assertEqual(set(job.engineer_users.all()), {self.engineer1, self.engineer2})
        self.assertEqual(job.import_source, "new.xlsx")

    def test_existing_job_can_clear_invoice_comments_and_lead(self):
        job = self.make_job_record(
            job_number="26001", invoice_status=Job.INVOICE_STATUS_PROGRESS,
            comments="Old comments", lead="Old Lead", lead_user=self.lead,
        )
        row = self.full_row(invoice="", comments="", lead="", customer="", engineer1="", engineer2="")
        with TemporaryDirectory() as directory:
            result = apply_job_import(self.workbook(directory, [row]))
        job.refresh_from_db()
        self.assertEqual(result.updated, 1)
        self.assertEqual(job.invoice_status, "")
        self.assertEqual(job.comments, "")
        self.assertEqual(job.lead, "")
        self.assertIsNone(job.lead_user)

    def test_preview_wrapper_matches_direct_import(self):
        with TemporaryDirectory() as directory:
            path = self.workbook(directory, [self.full_row()])
            direct = import_job_list(path, apply=False)
            wrapped = preview_job_import(path)
        self.assertEqual(direct.added, wrapped.added)
        self.assertEqual(direct.errors, wrapped.errors)
