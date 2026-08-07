from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files import File
from django.test import override_settings
from django.utils import timezone
from openpyxl import Workbook

from timesheets.models import Expense, Job, PartEntry, TimeEntry, Timesheet, TimesheetImport, WorkCode
from timesheets.services.importer import (
    _as_date,
    _clean,
    _find_chunk_date,
    _first_date_from_cells,
    _resolve_import_job,
    _time_row_to_date_and_order,
    _week_start,
    find_invalid_time_entry_job_numbers,
    import_timesheet_upload,
    parse_expense_entries,
    parse_part_entries,
    parse_time_entries,
    parse_week_start,
    valid_time_entry_job_qs,
)
from timesheets.tests.base import AppTestCase
from timesheets.tests.factories import write_timesheet_workbook


class ImporterHelperTests(AppTestCase):
    def test_clean_handles_blank_and_text_values(self):
        self.assertEqual(_clean(None), "")
        self.assertEqual(_clean(""), "")
        self.assertEqual(_clean("  value  "), "value")
        self.assertEqual(_clean(123), "123")

    def test_as_date_supports_date_datetime_and_strings(self):
        expected = date(2026, 8, 2)
        self.assertEqual(_as_date(expected), expected)
        self.assertEqual(_as_date(datetime(2026, 8, 2, 13, 30)), expected)
        self.assertEqual(_as_date("08/02/2026"), expected)
        self.assertEqual(_as_date("2026-08-02"), expected)
        self.assertEqual(_as_date("08/02/26"), expected)
        self.assertIsNone(_as_date("not-a-date"))

    def test_week_start_returns_sunday(self):
        self.assertEqual(_week_start(date(2026, 8, 6)), date(2026, 8, 2))
        self.assertEqual(_week_start(date(2026, 8, 2)), date(2026, 8, 2))

    def test_first_date_from_cells_returns_first_valid_date(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet["A1"] = "bad"
        worksheet["A2"] = date(2026, 8, 3)
        self.assertEqual(_first_date_from_cells(worksheet, ["A1", "A2"]), date(2026, 8, 3))

    def test_find_chunk_date_uses_explicit_or_previous_day(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet["A20"] = date(2026, 8, 2)
        self.assertEqual(_find_chunk_date(worksheet, 20, 24), date(2026, 8, 2))
        self.assertEqual(_find_chunk_date(worksheet, 25, 29, date(2026, 8, 2)), date(2026, 8, 3))
        self.assertIsNone(_find_chunk_date(worksheet, 25, 29))


class ImporterParsingTests(AppTestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "timesheet.xlsx"

    def test_parse_time_entries_reads_hours_description_and_overnight(self):
        write_timesheet_workbook(
            self.path,
            time_rows=[
                {
                    "row": 20,
                    "date": date(2026, 8, 2),
                    "job_number": "26001",
                    "work_code": "1000",
                    "regular": 8,
                    "overtime": 1.5,
                    "doubletime": 0.5,
                    "description": "Startup",
                    "overnight": "YES",
                },
                {"row": 21, "description": "Internal meeting", "regular": 2},
            ],
        )

        items = parse_time_entries(self.path)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].work_date, date(2026, 8, 2))
        self.assertEqual(items[0].row_order, 1)
        self.assertEqual(items[0].regular_hours, Decimal("8.00"))
        self.assertEqual(items[0].overtime_hours, Decimal("1.50"))
        self.assertEqual(items[0].doubletime_hours, Decimal("0.50"))
        self.assertTrue(items[0].overnight_stay)
        self.assertEqual(items[1].row_order, 2)

    def test_parse_time_entries_infers_following_dates_and_skips_blank_rows(self):
        write_timesheet_workbook(
            self.path,
            week_start=None,
            time_rows=[
                {"row": 20, "date": date(2026, 8, 2), "regular": 1, "description": "Sunday"},
                {"row": 25, "regular": 2, "description": "Monday"},
            ],
        )
        items = parse_time_entries(self.path)
        self.assertEqual([item.work_date for item in items], [date(2026, 8, 2), date(2026, 8, 3)])

    def test_time_row_mapping_covers_all_template_rows(self):
        write_timesheet_workbook(self.path, time_rows=[{"row": 20, "date": date(2026, 8, 2)}])
        mapping = _time_row_to_date_and_order(self.path)
        self.assertEqual(mapping[20], (date(2026, 8, 2), 1))
        self.assertEqual(mapping[24], (date(2026, 8, 2), 5))
        self.assertEqual(mapping[25], (date(2026, 8, 3), 1))
        self.assertEqual(mapping[54], (date(2026, 8, 8), 5))

    def test_parse_expenses_reads_values_and_skips_blank_rows(self):
        write_timesheet_workbook(
            self.path,
            time_rows=[{"row": 20, "date": date(2026, 8, 2), "regular": 1}],
            expense_rows=[
                {
                    "row": 9,
                    "miles": 25,
                    "per_diem_food": 37.5,
                    "air_fare": 100,
                    "hotel": 125,
                    "tolls_parking": 8,
                    "rental_car_fuel": 20,
                    "business_meals": 15,
                    "other_expense": 3,
                    "explanation": "Travel",
                }
            ],
        )
        items = parse_expense_entries(self.path)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].work_date, date(2026, 8, 2))
        self.assertEqual(items[0].row_order, 1)
        self.assertEqual(items[0].miles, Decimal("25.00"))
        self.assertEqual(items[0].hotel, Decimal("125.00"))
        self.assertEqual(items[0].explanation_of_expenses, "Travel")

    def test_parse_expenses_returns_empty_without_sheet(self):
        write_timesheet_workbook(self.path, include_expense_sheet=False)
        self.assertEqual(parse_expense_entries(self.path), [])

    def test_parse_parts_reads_values_and_skips_blank_rows(self):
        write_timesheet_workbook(
            self.path,
            time_rows=[{"row": 20, "date": date(2026, 8, 2), "regular": 1}],
            part_rows=[
                {
                    "row": 9,
                    "ee_stock_job_number": "26001",
                    "quantity": 2,
                    "description": "1769-L33ER",
                    "notes": "Replacement",
                    "reorder": "x",
                }
            ],
        )
        items = parse_part_entries(self.path)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].quantity, Decimal("2.00"))
        self.assertEqual(items[0].part_description_part_number, "1769-L33ER")
        self.assertTrue(items[0].reorder_part)

    def test_parse_parts_returns_empty_without_sheet(self):
        write_timesheet_workbook(self.path, include_parts_sheet=False)
        self.assertEqual(parse_part_entries(self.path), [])

    def test_parse_week_start_prefers_explicit_cell(self):
        write_timesheet_workbook(self.path, week_start=date(2026, 8, 5))
        self.assertEqual(parse_week_start(self.path), date(2026, 8, 2))

    def test_parse_week_start_falls_back_to_first_entry(self):
        write_timesheet_workbook(
            self.path,
            week_start=None,
            time_rows=[{"row": 20, "date": date(2026, 8, 6), "regular": 1}],
        )
        self.assertEqual(parse_week_start(self.path), date(2026, 8, 2))

    def test_parse_week_start_raises_when_no_dates_exist(self):
        write_timesheet_workbook(self.path, week_start=None)
        with self.assertRaisesMessage(ValueError, "Could not determine week start"):
            parse_week_start(self.path)


class ImporterJobValidationTests(AppTestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "timesheet.xlsx"
        self.valid_job = self.make_job_record(job_number="26001", description="Valid", active=True)
        self.make_job_record(job_number="26002", description="", active=True)
        self.make_job_record(job_number="26003", description="Inactive", active=False)

    def test_valid_job_queryset_requires_active_and_description(self):
        self.assertEqual(list(valid_time_entry_job_qs()), [self.valid_job])

    def test_invalid_job_numbers_are_grouped_with_unique_sample_descriptions(self):
        write_timesheet_workbook(
            self.path,
            time_rows=[
                {"row": 20, "date": date(2026, 8, 2), "job_number": "BAD", "regular": 1, "description": "One"},
                {"row": 21, "job_number": "BAD", "regular": 1, "description": "One"},
                {"row": 22, "job_number": "BAD", "regular": 1, "description": "Two"},
                {"row": 23, "job_number": "26001", "regular": 1},
                {"row": 24, "job_number": "", "regular": 1},
            ],
        )
        invalid = find_invalid_time_entry_job_numbers(self.path)
        self.assertEqual(invalid, {"BAD": {"count": 3, "descriptions": ["One", "Two"]}})

    def test_resolve_import_job_handles_blank_valid_correction_and_clear(self):
        self.assertEqual(_resolve_import_job(""), ("", None))
        self.assertEqual(_resolve_import_job("26001"), ("26001", self.valid_job))
        self.assertEqual(_resolve_import_job("BAD", {"BAD": "26001"}), ("26001", self.valid_job))
        self.assertEqual(_resolve_import_job("BAD", {"BAD": ""}), ("", None))

    def test_resolve_import_job_rejects_unavailable_job(self):
        with self.assertRaisesMessage(ValueError, "is not available for time entry"):
            _resolve_import_job("26003")


@override_settings(DEFAULT_FILE_STORAGE="django.core.files.storage.FileSystemStorage")
class ImportTimesheetUploadTests(AppTestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.tmp.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.employee = self.make_user(username="import_employee")
        self.job = self.make_job_record(job_number="26001", description="Valid", active=True)

    def create_upload(self, *, filename="timesheet.xlsx", **workbook_kwargs):
        source_path = Path(self.tmp.name) / f"source_{filename}"
        write_timesheet_workbook(source_path, **workbook_kwargs)
        upload = TimesheetImport(employee=self.employee)
        with source_path.open("rb") as source:
            upload.uploaded_file.save(filename, File(source), save=True)
        return upload

    def test_import_creates_timesheet_entries_work_code_expense_part_and_upload_status(self):
        upload = self.create_upload(
            time_rows=[
                {
                    "row": 20,
                    "date": date(2026, 8, 2),
                    "job_number": "26001",
                    "work_code": "TEST",
                    "regular": 8,
                    "overtime": 1,
                    "doubletime": 0.5,
                    "description": "Startup",
                    "overnight": True,
                }
            ],
            expense_rows=[{"row": 9, "miles": 10, "hotel": 125, "explanation": "Travel"}],
            part_rows=[{"row": 9, "ee_stock_job_number": "26001", "quantity": 2, "description": "PLC", "reorder": True}],
        )

        timesheet = import_timesheet_upload(upload)

        self.assertEqual(timesheet.week_start, date(2026, 8, 2))
        self.assertEqual(timesheet.status, Timesheet.Status.DRAFT)
        entry = timesheet.entries.get()
        self.assertEqual(entry.job, self.job)
        self.assertEqual(entry.work_code.code, "TEST")
        self.assertTrue(entry.overnight_stay)
        self.assertEqual(entry.regular_hours, Decimal("8.00"))
        self.assertEqual(entry.expense.miles, Decimal("10.00"))
        self.assertEqual(entry.expense.hotel.amount, Decimal("125.00"))
        self.assertEqual(entry.part_entry.quantity, Decimal("2.00"))
        upload.refresh_from_db()
        self.assertEqual(upload.imported_timesheet, timesheet)
        self.assertEqual(upload.status, "imported")
        self.assertIn("Existing records for the week were replaced", upload.message)

    def test_expense_only_row_creates_minimal_time_entry(self):
        upload = self.create_upload(
            time_rows=[{"row": 20, "date": date(2026, 8, 2)}],
            expense_rows=[{"row": 9, "miles": 12}],
        )
        timesheet = import_timesheet_upload(upload)
        entry = timesheet.entries.get()
        self.assertEqual(entry.regular_hours, Decimal("0.00"))
        self.assertEqual(entry.job_number, "")
        self.assertEqual(entry.expense.miles, Decimal("12.00"))

    def test_part_only_row_creates_minimal_time_entry_and_resolves_job(self):
        upload = self.create_upload(
            time_rows=[{"row": 20, "date": date(2026, 8, 2)}],
            part_rows=[{"row": 9, "ee_stock_job_number": "26001", "quantity": 1, "description": "Sensor"}],
        )
        timesheet = import_timesheet_upload(upload)
        entry = timesheet.entries.get()
        self.assertEqual(entry.job, self.job)
        self.assertEqual(entry.part_entry.ee_stock_job_number, "26001")

    def test_job_correction_replaces_invalid_job_or_clears_it(self):
        upload = self.create_upload(
            time_rows=[
                {"row": 20, "date": date(2026, 8, 2), "job_number": "BAD", "regular": 1},
                {"row": 21, "job_number": "CLEAR", "regular": 1},
            ],
        )
        timesheet = import_timesheet_upload(upload, {"BAD": "26001", "CLEAR": ""})
        entries = list(timesheet.entries.order_by("row_order"))
        self.assertEqual(entries[0].job, self.job)
        self.assertEqual(entries[0].job_number, "26001")
        self.assertIsNone(entries[1].job)
        self.assertEqual(entries[1].job_number, "")

    def test_invalid_job_rolls_back_timesheet_and_upload_changes(self):
        upload = self.create_upload(
            time_rows=[{"row": 20, "date": date(2026, 8, 2), "job_number": "BAD", "regular": 1}],
        )
        with self.assertRaises(ValueError):
            import_timesheet_upload(upload)
        self.assertFalse(Timesheet.objects.filter(employee=self.employee).exists())
        upload.refresh_from_db()
        self.assertEqual(upload.status, "pending")
        self.assertIsNone(upload.imported_timesheet)

    def test_reupload_replaces_existing_editable_week_and_resets_workflow_fields(self):
        timesheet = self.make_timesheet_record(
            employee=self.employee,
            week_start=date(2026, 8, 2),
            status=Timesheet.Status.REOPENED,
            submitted_at=timezone.now(),
            submitted_by=self.employee,
            approved_at=timezone.now(),
            approved_by=self.employee,
            invoiced_at=timezone.now(),
            invoiced_by=self.employee,
            deleted_at=timezone.now(),
            deleted_by=self.employee,
            delete_reason="old",
            reopen_reason="old",
            submission_export_format=Timesheet.ExportFormat.PDF,
        )
        old_entry = self.make_time_entry_record(timesheet=timesheet, regular_hours=Decimal("4.00"))
        PartEntry.objects.create(time_entry=old_entry, quantity=1, part_description_part_number="Old")
        upload = self.create_upload(
            time_rows=[{"row": 20, "date": date(2026, 8, 2), "job_number": "26001", "regular": 8}],
        )

        imported = import_timesheet_upload(upload)
        imported.refresh_from_db()
        self.assertEqual(imported.pk, timesheet.pk)
        self.assertEqual(imported.entries.count(), 1)
        self.assertEqual(imported.entries.get().regular_hours, Decimal("8.00"))
        self.assertEqual(PartEntry.objects.filter(time_entry__timesheet=imported).count(), 0)
        self.assertEqual(imported.status, Timesheet.Status.DRAFT)
        self.assertIsNone(imported.submitted_at)
        self.assertIsNone(imported.approved_at)
        self.assertIsNone(imported.invoiced_at)
        self.assertIsNone(imported.deleted_at)
        self.assertEqual(imported.reopen_reason, "")
        self.assertEqual(imported.submission_export_format, "")

    def test_locked_existing_week_cannot_be_replaced(self):
        for status in [
            Timesheet.Status.SUBMITTED,
            Timesheet.Status.APPROVED,
            Timesheet.Status.INVOICED,
            Timesheet.Status.VOID,
        ]:
            with self.subTest(status=status):
                Timesheet.objects.filter(employee=self.employee).delete()
                self.make_timesheet_record(employee=self.employee, week_start=date(2026, 8, 2), status=status)
                upload = self.create_upload(
                    filename=f"{status}.xlsx",
                    time_rows=[{"row": 20, "date": date(2026, 8, 2), "regular": 1}],
                )
                with self.assertRaisesMessage(ValueError, "cannot be replaced by upload"):
                    import_timesheet_upload(upload)

    def test_existing_work_code_is_reused(self):
        existing = WorkCode.objects.create(code="TEST", description="Existing")
        upload = self.create_upload(
            time_rows=[{"row": 20, "date": date(2026, 8, 2), "work_code": "TEST", "regular": 1}],
        )
        timesheet = import_timesheet_upload(upload)
        self.assertEqual(timesheet.entries.get().work_code, existing)
        self.assertEqual(WorkCode.objects.filter(code="TEST").count(), 1)
