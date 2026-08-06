import base64
import tempfile
import zipfile
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from .base import AppTestCase
from openpyxl import load_workbook
from pypdf import PdfReader
from decimal import Decimal

from accounts.models import EmployeeProfile
from timesheets.models import (
    Expense,
    PartEntry,
    TimeEntry,
    Timesheet,
    TimesheetReceipt,
    TimesheetSubmissionArtifact,
    WorkCode,
    MileageRate,
    OvernightRate,
)
from timesheets.services.exporter import (
    _export_initials_filename,
    build_timesheet_excel,
    build_timesheet_pdf,
)
from timesheets.services.receipts_pdf import (
    build_receipts_pdf_bytes,
    receipts_pdf_filename,
)
from timesheets.services.submission import create_timesheet_artifact
from timesheets.services.workbook_mapping import (
    DESCRIPTION_COL,
    JOB_COL,
    REGULAR_COL,
    TIME_ENTRY_CHUNKS,
    TIME_SHEET_NAME,
    WORK_CODE_COL,
)

User = get_user_model()


class TimesheetExportTestBase(AppTestCase):
    week_start = date(2026, 8, 2)

    @classmethod
    def setUpTestData(cls):
        cls.employee = User.objects.create_user(
            username="export.employee",
            password="test-password",
            first_name="Export",
            last_name="Employee",
            email="export.employee@gotoccs.com",
        )
        cls.other_employee = User.objects.create_user(
            username="other.employee",
            password="test-password",
            first_name="Other",
            last_name="Employee",
            email="other.employee@gotoccs.com",
        )
        cls.management_user = User.objects.create_user(
            username="export.management",
            password="test-password",
            first_name="Export",
            last_name="Manager",
            email="export.management@gotoccs.com",
        )
        management_group, _ = Group.objects.get_or_create(name="Management Staff")
        cls.management_user.groups.add(management_group)

        EmployeeProfile.objects.create(user=cls.employee)
        EmployeeProfile.objects.create(user=cls.other_employee)
        EmployeeProfile.objects.create(user=cls.management_user)

        cls.work_code, _ = WorkCode.objects.get_or_create(
            code="1800",
            defaults={"description": "Employee Development"},
        )

    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media_dir.cleanup)

    def make_timesheet(self, *, employee=None, status=Timesheet.Status.APPROVED, template_entries_per_day=5):
        return self.make_timesheet_record(
            employee=employee or self.employee,
            week_start=self.week_start,
            status=status,
            template_entries_per_day=template_entries_per_day,
            mileage_rate=Decimal("0.720"),
            overnight_rate=Decimal("50.00"),
        )

    def make_entry(self, timesheet, *, day_offset=0, row_order=1, **overrides):
        values = {
            "timesheet": timesheet,
            "work_date": timesheet.week_start + timedelta(days=day_offset),
            "row_order": row_order,
            "job_number": "26001",
            "work_code": self.work_code,
            "regular_hours": "8.00",
            "overtime_hours": "0.00",
            "doubletime_hours": "0.00",
            "description": "Export test work",
        }
        values.update(overrides)
        timesheet = values.pop("timesheet")
        work_date = values.pop("work_date")
        row_order = values.pop("row_order")
        return self.make_time_entry_record(
            timesheet=timesheet,
            work_date=work_date,
            row_order=row_order,
            **values,
        )

    def make_artifact(self, timesheet, *, employee=None, suffix="pdf", content=b"test artifact"):
        artifact = TimesheetSubmissionArtifact(
            timesheet=timesheet,
            file_type=suffix,
            export_format=(Timesheet.ExportFormat.PDF if suffix == "pdf" else Timesheet.ExportFormat.EXCEL),
            created_by=employee or timesheet.employee,
            submitted=True,
        )
        artifact.file.save(f"artifact.{suffix}", ContentFile(content), save=True)
        return artifact


class ExporterServiceTests(TimesheetExportTestBase):
    def test_export_filename_uses_week_and_employee_initials(self):
        timesheet = self.make_timesheet()
        self.assertEqual(_export_initials_filename(timesheet, "pdf"), "20260802_EE.pdf")

    def test_export_filename_falls_back_to_username(self):
        user = User.objects.create_user(username="xyuser", password="test-password")
        EmployeeProfile.objects.create(user=user)
        timesheet = self.make_timesheet(employee=user)
        self.assertEqual(_export_initials_filename(timesheet, "xlsx"), "20260802_XY.xlsx")

    def test_excel_export_writes_header_and_time_entry(self):
        timesheet = self.make_timesheet()
        self.make_entry(timesheet)

        export_path = build_timesheet_excel(timesheet)

        self.assertTrue(export_path.exists())
        workbook = load_workbook(export_path, data_only=False)
        worksheet = workbook[TIME_SHEET_NAME]
        first_row = TIME_ENTRY_CHUNKS[0][0]
        self.assertEqual(worksheet["M3"].value, "Export Employee")
        self.assertEqual(worksheet["F7"].value.date(), self.week_start)
        self.assertEqual(worksheet[f"{JOB_COL}{first_row}"].value, "26001")
        self.assertEqual(worksheet[f"{WORK_CODE_COL}{first_row}"].value, "1800")
        self.assertEqual(worksheet[f"{REGULAR_COL}{first_row}"].value, 8)
        self.assertEqual(worksheet[f"{DESCRIPTION_COL}{first_row}"].value, "Export test work")

    def test_excel_export_rejects_timesheet_over_template_limit(self):
        timesheet = self.make_timesheet(template_entries_per_day=5)
        for row_order in range(1, 7):
            self.make_entry(timesheet, row_order=row_order)

        with self.assertRaisesMessage(ValueError, "5 or fewer"):
            build_timesheet_excel(timesheet)

    def test_pdf_export_creates_readable_pdf_with_expense_and_parts_pages(self):
        timesheet = self.make_timesheet()
        entry = self.make_entry(timesheet, overnight_stay=True)

        Expense.objects.create(
            time_entry=entry,
            miles=Decimal("25.00"),
            hotel=Decimal("125.00"),
            business_meals=Decimal("32.50"),
        )

        PartEntry.objects.create(
            time_entry=entry,
            quantity=Decimal("2.00"),
            part_description_part_number="1769-L33ER",
            additional_notes_for_customer="Replacement controller",
            reorder_part=True,
        )

        export_path = build_timesheet_pdf(timesheet)

        self.assertTrue(export_path.exists())
        self.assertTrue(export_path.read_bytes().startswith(b"%PDF"))
        reader = PdfReader(str(export_path))
        self.assertGreaterEqual(len(reader.pages), 3)

        pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn(f"{self.week_start:%A} - {self.week_start:%m/%d/%Y}", pdf_text)
        self.assertIn("Daily Totals", pdf_text)
        self.assertIn("Weekly Totals", pdf_text)
        self.assertIn("Total Hours: 8.00", pdf_text)
        self.assertIn("Expense Report", pdf_text)
        self.assertIn("Totals", pdf_text)
        self.assertIn("Grand Total", pdf_text)
        self.assertIn("Overnight", pdf_text)
        self.assertIn("Stays: 1", pdf_text)
        self.assertIn("Rate: $50.00", pdf_text)
        self.assertIn("Overnight Total: $50.00", pdf_text)
        self.assertIn("$18.00", pdf_text)      # Mileage
        self.assertIn("$50.00", pdf_text)      # Overnight reimbursement
        self.assertIn("$125.00", pdf_text)     # Hotel
        self.assertIn("$32.50", pdf_text)      # Business meals
        self.assertIn("$175.50", pdf_text)     # Grand Total
        self.assertIn("Receipts", pdf_text)
        self.assertIn("No receipts were submitted for this timesheet.", pdf_text)

    def test_pdf_export_always_includes_expense_and_receipt_pages(self):
        timesheet = self.make_timesheet()
        self.make_entry(timesheet)

        export_path = build_timesheet_pdf(timesheet)
        reader = PdfReader(str(export_path))
        pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)

        self.assertIn("Expense Report", pdf_text)
        self.assertIn("Grand Total", pdf_text)
        self.assertIn("$0.00", pdf_text)
        self.assertIn("Receipts", pdf_text)
        self.assertIn("No receipts were submitted for this timesheet.", pdf_text)
        
    def test_overnight_rate_uses_exact_year_and_fallback(self):
        OvernightRate.objects.update_or_create(year=2026, defaults={"rate": Decimal("50.00")})
        self.assertEqual(OvernightRate.rate_for_date(date(2026, 8, 2)), Decimal("50.00"))
        self.assertEqual(OvernightRate.rate_for_date(date(2027, 8, 1)), Decimal("50.00"))

    def test_create_artifact_persists_generated_pdf(self):
        timesheet = self.make_timesheet()
        self.make_entry(timesheet)

        artifact = create_timesheet_artifact(
            timesheet,
            self.employee,
            Timesheet.ExportFormat.PDF,
            submitted=True,
        )

        self.assertEqual(artifact.file_type, "pdf")
        self.assertEqual(artifact.export_format, Timesheet.ExportFormat.PDF)
        self.assertTrue(artifact.submitted)
        self.assertEqual(artifact.created_by, self.employee)
        self.assertTrue(Path(artifact.file.path).exists())
        with artifact.file.open("rb") as artifact_file:
            self.assertEqual(artifact_file.read(4), b"%PDF")


class ReceiptPdfTests(TimesheetExportTestBase):
    def test_receipts_pdf_without_receipts_creates_one_page_pdf(self):
        timesheet = self.make_timesheet()
        pdf_bytes = build_receipts_pdf_bytes(timesheet)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertEqual(len(PdfReader(BytesIO(pdf_bytes)).pages), 1)

    def test_receipts_pdf_includes_uploaded_pdf_pages(self):
        timesheet = self.make_timesheet()
        source_pdf = build_receipts_pdf_bytes(timesheet)
        TimesheetReceipt.objects.create(
            timesheet=timesheet,
            uploaded_by=self.employee,
            file=SimpleUploadedFile("receipt.pdf", source_pdf, content_type="application/pdf"),
            original_filename="receipt.pdf",
        )

        combined_bytes = build_receipts_pdf_bytes(timesheet)

        self.assertTrue(combined_bytes.startswith(b"%PDF"))
        self.assertEqual(len(PdfReader(BytesIO(combined_bytes)).pages), 1)

    def test_receipts_pdf_includes_uploaded_image(self):
        timesheet = self.make_timesheet()
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZlqQAAAAASUVORK5CYII="
        )
        TimesheetReceipt.objects.create(
            timesheet=timesheet,
            uploaded_by=self.employee,
            file=SimpleUploadedFile("receipt.png", png_bytes, content_type="image/png"),
            original_filename="receipt.png",
            description="Lunch receipt",
        )

        pdf_bytes = build_receipts_pdf_bytes(timesheet)

        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertEqual(len(PdfReader(BytesIO(pdf_bytes)).pages), 1)

    def test_receipts_filename_uses_initials_and_week_start(self):
        timesheet = self.make_timesheet()
        self.assertEqual(receipts_pdf_filename(timesheet), "EE_20260802_receipts.pdf")


class ExportDownloadViewTests(TimesheetExportTestBase):
    @patch("timesheets.views.create_timesheet_artifact")
    def test_download_defaults_to_excel_and_redirects_to_ready_page(self, create_artifact):
        timesheet = self.make_timesheet(status=Timesheet.Status.DRAFT)
        artifact = self.make_artifact(timesheet, suffix="xlsx", content=b"xlsx")
        create_artifact.return_value = artifact
        self.client.force_login(self.employee)

        response = self.client.get(reverse("timesheet_download", args=[timesheet.pk]))

        create_artifact.assert_called_once_with(
            timesheet=timesheet,
            created_by=self.employee,
            export_format=Timesheet.ExportFormat.EXCEL,
            submitted=False,
        )
        self.assertRedirects(response, reverse("timesheet_download_ready", args=[artifact.pk]))

    @patch("timesheets.views.create_timesheet_artifact")
    def test_download_falls_back_to_pdf_when_excel_overflows(self, create_artifact):
        timesheet = self.make_timesheet(status=Timesheet.Status.DRAFT)
        for row_order in range(1, 7):
            self.make_entry(timesheet, row_order=row_order)
        artifact = self.make_artifact(timesheet, suffix="pdf", content=b"%PDF-test")
        create_artifact.return_value = artifact
        self.client.force_login(self.employee)

        response = self.client.get(
            reverse("timesheet_download", args=[timesheet.pk]),
            {"format": Timesheet.ExportFormat.EXCEL},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(create_artifact.call_args.kwargs["export_format"], Timesheet.ExportFormat.PDF)

    def test_owner_can_download_saved_artifact(self):
        timesheet = self.make_timesheet()
        artifact = self.make_artifact(timesheet, suffix="pdf", content=b"%PDF-owner")
        self.client.force_login(self.employee)

        response = self.client.get(reverse("timesheet_artifact_download", args=[artifact.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("20260802_EE.pdf", response["Content-Disposition"])

    def test_other_employee_cannot_download_saved_artifact(self):
        timesheet = self.make_timesheet()
        artifact = self.make_artifact(timesheet)
        self.client.force_login(self.other_employee)

        response = self.client.get(reverse("timesheet_artifact_download", args=[artifact.pk]))

        self.assertEqual(response.status_code, 404)

    def test_management_staff_can_download_saved_artifact(self):
        timesheet = self.make_timesheet()
        artifact = self.make_artifact(timesheet, suffix="xlsx", content=b"xlsx")
        self.client.force_login(self.management_user)

        response = self.client.get(reverse("timesheet_artifact_download", args=[artifact.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @patch("timesheets.views.build_receipts_pdf_bytes", return_value=b"%PDF-receipts")
    @patch("timesheets.views.create_timesheet_artifact")
    def test_package_download_contains_excel_pdf_and_receipts(self, create_artifact, build_receipts):
        timesheet = self.make_timesheet()
        excel_artifact = self.make_artifact(timesheet, suffix="xlsx", content=b"excel-content")
        pdf_artifact = self.make_artifact(timesheet, suffix="pdf", content=b"%PDF-content")
        create_artifact.side_effect = [excel_artifact, pdf_artifact]
        self.client.force_login(self.employee)

        response = self.client.get(reverse("timesheet_package_download", args=[timesheet.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertIn('filename="20260802_EE.zip"', response["Content-Disposition"])
        archive = zipfile.ZipFile(BytesIO(response.content))
        self.assertEqual(
            set(archive.namelist()),
            {
                "20260802_EE.xlsx",
                "20260802_EE.pdf",
                "20260802_EE_Receipts.pdf",
            },
        )
        self.assertEqual(archive.read("20260802_EE.xlsx"), b"excel-content")
        self.assertEqual(archive.read("20260802_EE.pdf"), b"%PDF-content")
        self.assertEqual(archive.read("20260802_EE_Receipts.pdf"), b"%PDF-receipts")
        build_receipts.assert_called_once_with(timesheet)

    @patch("timesheets.views.create_timesheet_artifact")
    def test_package_download_rejects_excel_overflow(self, create_artifact):
        timesheet = self.make_timesheet()
        for row_order in range(1, 7):
            self.make_entry(timesheet, row_order=row_order)
        self.client.force_login(self.employee)

        response = self.client.get(reverse("timesheet_package_download", args=[timesheet.pk]))

        self.assertRedirects(response, reverse("timesheet_submitted", args=[timesheet.pk]))
        create_artifact.assert_not_called()
