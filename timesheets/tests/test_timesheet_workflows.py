from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import EmployeeProfile
from timesheets.models import (
    BulkImportJob,
    TimeEntry,
    Timesheet,
    TimesheetReceipt,
)
from .base import AppTestCase


class TimesheetWorkflowBase(AppTestCase):
    week_start = date(2026, 8, 2)

    @classmethod
    def setUpTestData(cls):
        cls.employee = cls.make_user(
            username="workflow_employee",
            first_name="Workflow",
            last_name="Employee",
        )
        cls.other_employee = cls.make_user(
            username="workflow_other",
            first_name="Other",
            last_name="Employee",
        )
        cls.manager = cls.make_user(
            username="workflow_manager",
            first_name="Project",
            last_name="Manager",
        )
        cls.management = cls.make_user(
            username="workflow_management",
            first_name="Management",
            last_name="User",
            is_staff=True,
        )
        cls.add_to_group(cls.manager, "ProjectManagers")
        cls.add_to_group(cls.management, "Management Staff")
        EmployeeProfile.objects.create(user=cls.employee, supervisor=cls.manager)
        EmployeeProfile.objects.create(user=cls.other_employee)
        EmployeeProfile.objects.create(user=cls.manager)
        EmployeeProfile.objects.create(user=cls.management)

    def make_timesheet(self, *, employee=None, status=Timesheet.Status.DRAFT, week_start=None, **overrides):
        return self.make_timesheet_record(
            employee=employee or self.employee,
            week_start=week_start or self.week_start,
            status=status,
            **overrides,
        )

    def add_entry(self, timesheet, *, work_date=None, row_order=1, regular="8.00", **overrides):
        return self.make_time_entry_record(
            timesheet=timesheet,
            work_date=work_date or timesheet.week_start,
            row_order=row_order,
            regular_hours=Decimal(regular),
            **overrides,
        )


class TimesheetListAndDetailTests(TimesheetWorkflowBase):
    def test_list_only_contains_logged_in_users_non_deleted_timesheets(self):
        visible = self.make_timesheet()
        self.make_timesheet(week_start=self.week_start + timedelta(days=7), deleted_at=timezone.now())
        self.make_timesheet(employee=self.other_employee)
        self.login(self.employee)

        response = self.client.get(reverse("timesheet_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["page_obj"].object_list), [visible])

    def test_list_annotates_total_hours_and_orders_newest_first(self):
        older = self.make_timesheet()
        newer = self.make_timesheet(week_start=self.week_start + timedelta(days=7))
        self.add_entry(older, regular="3.00", overtime_hours=Decimal("2.00"), doubletime_hours=Decimal("1.00"))
        self.add_entry(newer, regular="7.00")
        self.login(self.employee)

        response = self.client.get(reverse("timesheet_list"))

        rows = list(response.context["page_obj"].object_list)
        self.assertEqual(rows, [newer, older])
        self.assertEqual(rows[0].total_hours, Decimal("7.00"))
        self.assertEqual(rows[1].total_hours, Decimal("6.00"))

    def test_list_paginates_twenty_five_timesheets(self):
        for offset in range(26):
            self.make_timesheet(week_start=self.week_start + timedelta(days=offset * 7))
        self.login(self.employee)

        response = self.client.get(reverse("timesheet_list"), {"page": 2})

        self.assertEqual(response.context["page_obj"].paginator.per_page, 25)
        self.assertEqual(len(response.context["page_obj"].object_list), 1)

    def test_detail_contains_weekly_total_and_history(self):
        timesheet = self.make_timesheet()
        self.add_entry(timesheet, regular="8.00")
        self.add_entry(timesheet, work_date=self.week_start + timedelta(days=1), regular="4.00")
        self.login(self.employee)

        response = self.client.get(reverse("timesheet_detail", args=[timesheet.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["weekly_total_hours"], Decimal("12.00"))
        self.assertIn("history", response.context)

    def test_detail_exposes_pending_reopen_request(self):
        timesheet = self.make_timesheet(status=Timesheet.Status.APPROVED)
        request = timesheet.reopen_requests.create(
            requested_by=self.employee,
            supervisor=self.manager,
            reason="Need correction",
        )
        self.login(self.employee)

        response = self.client.get(reverse("timesheet_detail", args=[timesheet.pk]))

        self.assertEqual(response.context["pending_reopen_request"], request)

    def test_submitted_page_redirects_draft_to_detail(self):
        timesheet = self.make_timesheet()
        self.login(self.employee)

        response = self.client.get(reverse("timesheet_submitted", args=[timesheet.pk]))

        self.assertRedirects(response, reverse("timesheet_detail", args=[timesheet.pk]))

    def test_submitted_page_renders_for_submitted_timesheet(self):
        timesheet = self.make_timesheet(status=Timesheet.Status.SUBMITTED)
        self.login(self.employee)

        response = self.client.get(reverse("timesheet_submitted", args=[timesheet.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["timesheet"], timesheet)


class ReceiptWorkflowTests(TimesheetWorkflowBase):
    def setUp(self):
        super().setUp()
        self.temp_media = TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.temp_media.cleanup)

    def make_receipt(self, timesheet, *, owner=None, name="receipt.txt", content=b"receipt-data"):
        return TimesheetReceipt.objects.create(
            timesheet=timesheet,
            uploaded_by=owner or timesheet.employee,
            file=SimpleUploadedFile(name, content, content_type="text/plain"),
            original_filename=name,
            description="Test receipt",
        )

    def test_upload_requires_post(self):
        timesheet = self.make_timesheet()
        self.login(self.employee)

        response = self.client.get(reverse("timesheet_receipt_upload", args=[timesheet.pk]))

        self.assertRedirects(response, reverse("timesheet_detail", args=[timesheet.pk]))
        self.assertEqual(timesheet.receipts.count(), 0)

    def test_upload_requires_at_least_one_file(self):
        timesheet = self.make_timesheet()
        self.login(self.employee)

        response = self.client.post(reverse("timesheet_receipt_upload", args=[timesheet.pk]))

        self.assertRedirects(response, reverse("timesheet_detail", args=[timesheet.pk]))
        self.assertEqual(timesheet.receipts.count(), 0)

    def test_owner_can_upload_multiple_receipts_with_description(self):
        timesheet = self.make_timesheet()
        self.login(self.employee)
        files = [
            SimpleUploadedFile("one.txt", b"one"),
            SimpleUploadedFile("two.txt", b"two"),
        ]

        response = self.client.post(
            reverse("timesheet_receipt_upload", args=[timesheet.pk]),
            {"receipt_files": files, "receipt_description": "Travel receipts"},
        )

        self.assertRedirects(response, reverse("timesheet_detail", args=[timesheet.pk]))
        self.assertEqual(timesheet.receipts.count(), 2)
        self.assertEqual(set(timesheet.receipts.values_list("original_filename", flat=True)), {"one.txt", "two.txt"})
        self.assertEqual(set(timesheet.receipts.values_list("description", flat=True)), {"Travel receipts"})

    def test_receipt_upload_is_blocked_when_timesheet_locked(self):
        timesheet = self.make_timesheet(status=Timesheet.Status.SUBMITTED)
        self.login(self.employee)

        response = self.client.post(
            reverse("timesheet_receipt_upload", args=[timesheet.pk]),
            {"receipt_files": [SimpleUploadedFile("one.txt", b"one")]},
        )

        self.assertRedirects(response, reverse("timesheet_detail", args=[timesheet.pk]))
        self.assertEqual(timesheet.receipts.count(), 0)

    def test_user_cannot_upload_to_another_employees_timesheet(self):
        timesheet = self.make_timesheet(employee=self.other_employee)
        self.login(self.employee)

        response = self.client.post(
            reverse("timesheet_receipt_upload", args=[timesheet.pk]),
            {"receipt_files": [SimpleUploadedFile("one.txt", b"one")]},
        )

        self.assertEqual(response.status_code, 404)

    def test_owner_can_download_receipt_inline(self):
        timesheet = self.make_timesheet()
        receipt = self.make_receipt(timesheet)
        self.login(self.employee)

        response = self.client.get(reverse("timesheet_receipt_download", args=[receipt.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(b"".join(response.streaming_content), b"receipt-data")

    def test_management_can_download_other_users_receipt(self):
        timesheet = self.make_timesheet(employee=self.other_employee)
        receipt = self.make_receipt(timesheet)
        self.login(self.management)

        response = self.client.get(reverse("timesheet_receipt_download", args=[receipt.pk]))

        self.assertEqual(response.status_code, 200)

    def test_regular_user_cannot_download_other_users_receipt(self):
        timesheet = self.make_timesheet(employee=self.other_employee)
        receipt = self.make_receipt(timesheet)
        self.login(self.employee)

        response = self.client.get(reverse("timesheet_receipt_download", args=[receipt.pk]))

        self.assertEqual(response.status_code, 404)

    @patch("timesheets.views.build_receipts_pdf_bytes", return_value=b"%PDF-test")
    @patch("timesheets.views.receipts_pdf_filename", return_value="receipts.pdf")
    def test_authorized_user_can_download_receipts_pdf(self, filename, build_pdf):
        timesheet = self.make_timesheet()
        self.login(self.employee)

        response = self.client.get(reverse("timesheet_receipts_pdf", args=[timesheet.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"%PDF-test")
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="receipts.pdf"')
        build_pdf.assert_called_once_with(timesheet)

    def test_unauthorized_user_cannot_download_receipts_pdf(self):
        timesheet = self.make_timesheet(employee=self.other_employee)
        self.login(self.employee)

        response = self.client.get(reverse("timesheet_receipts_pdf", args=[timesheet.pk]))

        self.assertEqual(response.status_code, 404)

    def test_delete_requires_post(self):
        timesheet = self.make_timesheet()
        receipt = self.make_receipt(timesheet)
        self.login(self.employee)

        response = self.client.get(reverse("timesheet_receipt_delete", args=[receipt.pk]))

        self.assertRedirects(response, reverse("timesheet_detail", args=[timesheet.pk]))
        self.assertTrue(TimesheetReceipt.objects.filter(pk=receipt.pk).exists())

    def test_owner_can_delete_receipt_and_file(self):
        timesheet = self.make_timesheet()
        receipt = self.make_receipt(timesheet)
        saved_path = Path(receipt.file.path)
        self.assertTrue(saved_path.exists())
        self.login(self.employee)

        response = self.client.post(reverse("timesheet_receipt_delete", args=[receipt.pk]))

        self.assertRedirects(response, reverse("timesheet_detail", args=[timesheet.pk]))
        self.assertFalse(TimesheetReceipt.objects.filter(pk=receipt.pk).exists())
        self.assertFalse(saved_path.exists())

    def test_receipt_delete_is_blocked_when_timesheet_locked(self):
        timesheet = self.make_timesheet(status=Timesheet.Status.APPROVED)
        receipt = self.make_receipt(timesheet)
        self.login(self.employee)

        response = self.client.post(reverse("timesheet_receipt_delete", args=[receipt.pk]))

        self.assertRedirects(response, reverse("timesheet_detail", args=[timesheet.pk]))
        self.assertTrue(TimesheetReceipt.objects.filter(pk=receipt.pk).exists())

    def test_user_cannot_delete_another_users_receipt(self):
        timesheet = self.make_timesheet(employee=self.other_employee)
        receipt = self.make_receipt(timesheet)
        self.login(self.employee)

        response = self.client.post(reverse("timesheet_receipt_delete", args=[receipt.pk]))

        self.assertEqual(response.status_code, 404)


class DeleteAndReopenWorkflowTests(TimesheetWorkflowBase):
    def test_delete_get_renders_confirmation_form(self):
        timesheet = self.make_timesheet()
        self.login(self.employee)

        response = self.client.get(reverse("timesheet_delete", args=[timesheet.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["timesheet"], timesheet)

    def test_draft_delete_soft_deletes_without_voiding(self):
        timesheet = self.make_timesheet()
        self.login(self.employee)

        response = self.client.post(reverse("timesheet_delete", args=[timesheet.pk]), {"reason": "Duplicate"})

        timesheet.refresh_from_db()
        self.assertRedirects(response, reverse("timesheet_list"))
        self.assertEqual(timesheet.status, Timesheet.Status.DRAFT)
        self.assertEqual(timesheet.deleted_by, self.employee)
        self.assertEqual(timesheet.delete_reason, "Duplicate")
        self.assertIsNotNone(timesheet.deleted_at)

    def test_submitted_delete_marks_timesheet_void(self):
        timesheet = self.make_timesheet(status=Timesheet.Status.SUBMITTED)
        self.login(self.employee)

        self.client.post(reverse("timesheet_delete", args=[timesheet.pk]), {"reason": "Wrong week"})

        timesheet.refresh_from_db()
        self.assertEqual(timesheet.status, Timesheet.Status.VOID)
        self.assertIsNotNone(timesheet.deleted_at)

    def test_regular_employee_cannot_delete_approved_timesheet(self):
        timesheet = self.make_timesheet(status=Timesheet.Status.APPROVED)
        self.login(self.employee)

        response = self.client.post(reverse("timesheet_delete", args=[timesheet.pk]), {"reason": "Remove"})

        timesheet.refresh_from_db()
        self.assertRedirects(response, reverse("timesheet_detail", args=[timesheet.pk]))
        self.assertIsNone(timesheet.deleted_at)
        self.assertEqual(timesheet.status, Timesheet.Status.APPROVED)

    def test_user_cannot_delete_another_employees_timesheet(self):
        timesheet = self.make_timesheet(employee=self.other_employee)
        self.login(self.employee)

        response = self.client.post(reverse("timesheet_delete", args=[timesheet.pk]))

        self.assertEqual(response.status_code, 404)

    def test_reopen_get_only_allows_submitted_timesheet(self):
        draft = self.make_timesheet()
        self.login(self.employee)

        response = self.client.get(reverse("timesheet_reopen", args=[draft.pk]))

        self.assertRedirects(response, reverse("timesheet_detail", args=[draft.pk]))

    @patch("timesheets.views.send_reopened_admin_notification")
    def test_owner_can_reopen_submitted_timesheet(self, notify):
        timesheet = self.make_timesheet(status=Timesheet.Status.SUBMITTED)
        self.login(self.employee)

        response = self.client.post(
            reverse("timesheet_reopen", args=[timesheet.pk]),
            {"reason": "Correct overtime"},
        )

        timesheet.refresh_from_db()
        self.assertEqual(timesheet.status, Timesheet.Status.REOPENED)
        self.assertEqual(timesheet.reopened_by, self.employee)
        self.assertEqual(timesheet.reopen_reason, "Correct overtime")
        self.assertIsNotNone(timesheet.reopened_at)
        notify.assert_called_once()
        self.assertRedirects(response, reverse("timesheet_edit", args=[timesheet.pk]))

    def test_reopen_requires_reason(self):
        timesheet = self.make_timesheet(status=Timesheet.Status.SUBMITTED)
        self.login(self.employee)

        response = self.client.post(reverse("timesheet_reopen", args=[timesheet.pk]), {"reason": ""})

        timesheet.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(timesheet.status, Timesheet.Status.SUBMITTED)

    def test_reopen_only_works_for_owner(self):
        timesheet = self.make_timesheet(employee=self.other_employee, status=Timesheet.Status.SUBMITTED)
        self.login(self.employee)

        response = self.client.post(reverse("timesheet_reopen", args=[timesheet.pk]), {"reason": "Fix"})

        self.assertEqual(response.status_code, 404)


class BulkUploadStatusTests(TimesheetWorkflowBase):
    def make_job(self, *, employee=None, status="pending"):
        return BulkImportJob.objects.create(
            employee=employee or self.employee,
            uploaded_zip=SimpleUploadedFile("timesheets.zip", b"PK-test", content_type="application/zip"),
            status=status,
            total_files=3,
            processed_files=2,
            imported_files=1,
            failed_files=1,
            results_json=[{"filename": "one.xlsx", "status": "imported"}],
        )

    def setUp(self):
        super().setUp()
        self.temp_media = TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.temp_media.cleanup)

    def test_owner_can_open_bulk_status_page(self):
        job = self.make_job()
        self.login(self.employee)

        response = self.client.get(reverse("timesheet_bulk_zip_upload_status", args=[job.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["job"], job)

    def test_other_user_cannot_open_bulk_status_page(self):
        job = self.make_job(employee=self.other_employee)
        self.login(self.employee)

        response = self.client.get(reverse("timesheet_bulk_zip_upload_status", args=[job.pk]))

        self.assertEqual(response.status_code, 404)

    def test_bulk_status_api_returns_progress_and_completion(self):
        job = self.make_job(status="completed")
        self.login(self.employee)

        response = self.client.get(reverse("timesheet_bulk_zip_upload_status_api", args=[job.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "status": "completed",
            "total_files": 3,
            "processed_files": 2,
            "imported_files": 1,
            "failed_files": 1,
            "results": [{"filename": "one.xlsx", "status": "imported"}],
            "completed": True,
        })

    def test_bulk_status_api_marks_running_job_incomplete(self):
        job = self.make_job(status="running")
        self.login(self.employee)

        response = self.client.get(reverse("timesheet_bulk_zip_upload_status_api", args=[job.pk]))

        self.assertFalse(response.json()["completed"])
