from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import EmployeeProfile
from timesheets.models import (
    Job,
    TimeEntry,
    Timesheet,
    TimesheetImport,
    TimesheetReopenRequest,
    TimesheetSubmissionArtifact,
)
from timesheets.tests.base import AppTestCase


class ManagementWorkflowBase(AppTestCase):
    week_start = date(2026, 8, 2)

    @classmethod
    def setUpTestData(cls):
        cls.employee = cls.make_user(
            username="employee",
            first_name="Test",
            last_name="Employee",
        )
        cls.other_employee = cls.make_user(
            username="other_employee",
            first_name="Other",
            last_name="Employee",
        )
        cls.manager = cls.make_user(
            username="manager",
            first_name="Project",
            last_name="Manager",
        )
        cls.other_manager = cls.make_user(
            username="other_manager",
            first_name="Other",
            last_name="Manager",
        )
        cls.management = cls.make_user(
            username="management",
            first_name="Management",
            last_name="User",
        )
        cls.add_to_group(cls.manager, "ProjectManagers")
        cls.add_to_group(cls.other_manager, "ProjectManagers")
        cls.add_to_group(cls.management, "Management Staff")

        EmployeeProfile.objects.create(user=cls.employee, supervisor=cls.manager)
        EmployeeProfile.objects.create(user=cls.other_employee, supervisor=cls.other_manager)
        EmployeeProfile.objects.create(user=cls.manager)
        EmployeeProfile.objects.create(user=cls.other_manager)
        EmployeeProfile.objects.create(user=cls.management)

        cls.valid_job = Job.objects.create(
            job_number="26001",
            description="Valid project",
            job_status=Job.STATUS_ACTIVE,
            active=True,
        )

    def make_timesheet(self, *, employee=None, status=Timesheet.Status.DRAFT, week_start=None, **kwargs):
        return self.make_timesheet_record(
            employee=employee or self.employee,
            week_start=week_start or self.week_start,
            status=status,
            **kwargs,
        )

    def make_entry(self, timesheet, *, job=None, job_number="26001", work_date=None, **kwargs):
        return self.make_time_entry_record(
            timesheet=timesheet,
            work_date=work_date or timesheet.week_start,
            job=job,
            job_number=job_number,
            **kwargs,
        )

    def make_upload(self, *, employee=None, filename="timesheet.xlsx"):
        return TimesheetImport.objects.create(
            employee=employee or self.employee,
            uploaded_file=SimpleUploadedFile(
                filename,
                b"not-a-real-workbook",
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )


class ApprovalQueueAndDecisionTests(ManagementWorkflowBase):
    def test_regular_employee_cannot_open_approval_queue(self):
        self.login(self.employee)
        response = self.client.get(reverse("timesheet_approvals"))
        self.assertRedirects(response, reverse("timesheet_list"))

    def test_management_sees_all_submitted_non_deleted_timesheets(self):
        first = self.make_timesheet(status=Timesheet.Status.SUBMITTED)
        second = self.make_timesheet(
            employee=self.other_employee,
            status=Timesheet.Status.SUBMITTED,
        )
        self.make_timesheet(
            employee=self.manager,
            status=Timesheet.Status.APPROVED,
        )
        self.make_timesheet(
            employee=self.other_manager,
            status=Timesheet.Status.SUBMITTED,
            deleted_at=timezone.now(),
        )
        self.login(self.management)

        response = self.client.get(reverse("timesheet_approvals"))

        self.assertEqual(list(response.context["timesheets"]), [second, first])

    def test_approve_get_redirects_without_changing_status(self):
        timesheet = self.make_timesheet(status=Timesheet.Status.SUBMITTED)
        self.login(self.manager)

        response = self.client.get(reverse("timesheet_approve", args=[timesheet.pk]))

        timesheet.refresh_from_db()
        self.assertEqual(timesheet.status, Timesheet.Status.SUBMITTED)
        self.assertRedirects(response, timesheet.get_absolute_url())

    @patch("timesheets.views.approve_timesheet", side_effect=ValueError("bad state"))
    def test_approve_service_error_leaves_timesheet_submitted(self, approve_mock):
        timesheet = self.make_timesheet(status=Timesheet.Status.SUBMITTED)
        self.login(self.manager)

        response = self.client.post(reverse("timesheet_approve", args=[timesheet.pk]))

        timesheet.refresh_from_db()
        self.assertEqual(timesheet.status, Timesheet.Status.SUBMITTED)
        approve_mock.assert_called_once()
        self.assertRedirects(response, reverse("timesheet_approvals"))

    @patch("timesheets.views.send_employee_timesheet_approved_email", side_effect=RuntimeError("employee mail"))
    @patch("timesheets.views.send_timesheet_approved_email", side_effect=RuntimeError("admin mail"))
    def test_approval_remains_successful_when_both_emails_fail(self, _admin_email, _employee_email):
        timesheet = self.make_timesheet(status=Timesheet.Status.SUBMITTED)
        self.login(self.manager)

        response = self.client.post(reverse("timesheet_approve", args=[timesheet.pk]))

        timesheet.refresh_from_db()
        self.assertEqual(timesheet.status, Timesheet.Status.APPROVED)
        self.assertRedirects(response, reverse("timesheet_approvals"))

    def test_reject_get_renders_form_for_submitted_timesheet(self):
        timesheet = self.make_timesheet(status=Timesheet.Status.SUBMITTED)
        self.login(self.manager)

        response = self.client.get(reverse("timesheet_reject", args=[timesheet.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["timesheet"], timesheet)

    def test_reject_non_submitted_timesheet_redirects_without_change(self):
        timesheet = self.make_timesheet(status=Timesheet.Status.APPROVED)
        self.login(self.manager)

        response = self.client.post(
            reverse("timesheet_reject", args=[timesheet.pk]),
            {"reason": "No longer valid"},
        )

        timesheet.refresh_from_db()
        self.assertEqual(timesheet.status, Timesheet.Status.APPROVED)
        self.assertRedirects(response, timesheet.get_absolute_url())

    def test_reject_requires_reason(self):
        timesheet = self.make_timesheet(status=Timesheet.Status.SUBMITTED)
        self.login(self.manager)

        response = self.client.post(reverse("timesheet_reject", args=[timesheet.pk]), {"reason": ""})

        timesheet.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(timesheet.status, Timesheet.Status.SUBMITTED)
        self.assertTrue(response.context["form"].errors)

    @patch("timesheets.views.send_employee_timesheet_rejected_email", side_effect=RuntimeError("mail down"))
    def test_rejection_persists_when_employee_email_fails(self, _send_email):
        timesheet = self.make_timesheet(status=Timesheet.Status.SUBMITTED)
        self.login(self.manager)

        response = self.client.post(
            reverse("timesheet_reject", args=[timesheet.pk]),
            {"reason": "Correct the hours."},
        )

        timesheet.refresh_from_db()
        self.assertEqual(timesheet.status, Timesheet.Status.REJECTED)
        self.assertRedirects(response, reverse("timesheet_approvals"))

    def test_regular_employee_cannot_mark_timesheet_invoiced(self):
        timesheet = self.make_timesheet(status=Timesheet.Status.APPROVED)
        self.login(self.employee)

        response = self.client.post(reverse("timesheet_mark_invoiced", args=[timesheet.pk]))

        timesheet.refresh_from_db()
        self.assertEqual(timesheet.status, Timesheet.Status.APPROVED)
        self.assertRedirects(response, reverse("timesheet_list"))

    def test_mark_invoiced_get_does_not_change_timesheet(self):
        timesheet = self.make_timesheet(status=Timesheet.Status.APPROVED)
        self.login(self.management)

        response = self.client.get(reverse("timesheet_mark_invoiced", args=[timesheet.pk]))

        timesheet.refresh_from_db()
        self.assertEqual(timesheet.status, Timesheet.Status.APPROVED)
        self.assertRedirects(response, timesheet.get_absolute_url())

    def test_mark_invoiced_invalid_state_stays_unchanged(self):
        timesheet = self.make_timesheet(status=Timesheet.Status.SUBMITTED)
        self.login(self.management)

        response = self.client.post(reverse("timesheet_mark_invoiced", args=[timesheet.pk]))

        timesheet.refresh_from_db()
        self.assertEqual(timesheet.status, Timesheet.Status.SUBMITTED)
        self.assertRedirects(response, timesheet.get_absolute_url())


class ReopenRequestManagementTests(ManagementWorkflowBase):
    def make_reopen_request(self, *, timesheet=None, priority="low", status="pending"):
        timesheet = timesheet or self.make_timesheet(status=Timesheet.Status.APPROVED)
        return TimesheetReopenRequest.objects.create(
            timesheet=timesheet,
            requested_by=timesheet.employee,
            supervisor=self.manager,
            reason="Correction needed.",
            priority=priority,
            status=status,
        )

    def test_project_manager_without_management_group_cannot_manage_requests(self):
        request_obj = self.make_reopen_request()
        self.login(self.manager)

        for name, args in [
            ("reopen_request_list", []),
            ("reopen_request_review", [request_obj.pk]),
            ("reopen_request_approve", [request_obj.pk]),
            ("reopen_request_reject", [request_obj.pk]),
        ]:
            with self.subTest(name=name):
                response = self.client.get(reverse(name, args=args))
                self.assertRedirects(response, reverse("timesheet_list"))

    def test_list_contains_only_pending_requests_in_database_priority_order(self):
        high = self.make_reopen_request(priority="high")
        low = self.make_reopen_request(
            timesheet=self.make_timesheet(
                employee=self.other_employee,
                status=Timesheet.Status.APPROVED,
            ),
            priority="low",
        )
        self.make_reopen_request(
            timesheet=self.make_timesheet(
                employee=self.manager,
                status=Timesheet.Status.APPROVED,
            ),
            status="approved",
        )
        self.login(self.management)

        response = self.client.get(reverse("reopen_request_list"))

        self.assertEqual(list(response.context["requests"]), [high, low])

    def test_review_page_exposes_request_and_timesheet(self):
        request_obj = self.make_reopen_request()
        self.login(self.management)

        response = self.client.get(reverse("reopen_request_review", args=[request_obj.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["reopen_request"], request_obj)
        self.assertEqual(response.context["timesheet"], request_obj.timesheet)

    def test_approve_get_redirects_to_review(self):
        request_obj = self.make_reopen_request()
        self.login(self.management)

        response = self.client.get(reverse("reopen_request_approve", args=[request_obj.pk]))

        request_obj.refresh_from_db()
        self.assertEqual(request_obj.status, "pending")
        self.assertRedirects(response, reverse("reopen_request_review", args=[request_obj.pk]))

    @patch("timesheets.views.send_reopened_admin_notification", side_effect=RuntimeError("admin mail"))
    @patch("timesheets.views.send_employee_reopen_approved_email", side_effect=RuntimeError("employee mail"))
    def test_approve_persists_when_notifications_fail(self, _employee_email, _admin_email):
        request_obj = self.make_reopen_request()
        self.login(self.management)

        response = self.client.post(
            reverse("reopen_request_approve", args=[request_obj.pk]),
            {"decision_notes": "Approved despite mail errors."},
        )

        request_obj.refresh_from_db()
        request_obj.timesheet.refresh_from_db()
        self.assertEqual(request_obj.status, "approved")
        self.assertEqual(request_obj.decision_notes, "Approved despite mail errors.")
        self.assertEqual(request_obj.timesheet.status, Timesheet.Status.REOPENED)
        self.assertRedirects(response, reverse("reopen_request_list"))

    def test_approve_only_accepts_pending_request(self):
        request_obj = self.make_reopen_request(status="approved")
        self.login(self.management)

        response = self.client.post(reverse("reopen_request_approve", args=[request_obj.pk]))

        self.assertEqual(response.status_code, 404)

    def test_reject_get_redirects_to_review(self):
        request_obj = self.make_reopen_request()
        self.login(self.management)

        response = self.client.get(reverse("reopen_request_reject", args=[request_obj.pk]))

        request_obj.refresh_from_db()
        self.assertEqual(request_obj.status, "pending")
        self.assertRedirects(response, reverse("reopen_request_review", args=[request_obj.pk]))

    @patch("timesheets.views.send_employee_reopen_rejected_email", side_effect=RuntimeError("mail down"))
    def test_reject_persists_when_notification_fails(self, _send_email):
        request_obj = self.make_reopen_request()
        self.login(self.management)

        response = self.client.post(
            reverse("reopen_request_reject", args=[request_obj.pk]),
            {"decision_notes": "Not approved."},
        )

        request_obj.refresh_from_db()
        request_obj.timesheet.refresh_from_db()
        self.assertEqual(request_obj.status, "denied")
        self.assertEqual(request_obj.decision_notes, "Not approved.")
        self.assertEqual(request_obj.timesheet.status, Timesheet.Status.APPROVED)
        self.assertRedirects(response, reverse("reopen_request_list"))

    def test_reject_only_accepts_pending_request(self):
        request_obj = self.make_reopen_request(status="denied")
        self.login(self.management)

        response = self.client.post(reverse("reopen_request_reject", args=[request_obj.pk]))

        self.assertEqual(response.status_code, 404)


class InvalidJobCleanupTests(ManagementWorkflowBase):
    def make_invalid_job_with_entries(self):
        invalid = Job.objects.create(
            job_number="BAD-001",
            description="",
            job_status=Job.STATUS_UNKNOWN,
            active=False,
        )
        first_sheet = self.make_timesheet()
        second_sheet = self.make_timesheet(
            employee=self.other_employee,
            week_start=self.week_start + timedelta(days=7),
        )
        first = self.make_entry(
            first_sheet,
            job=invalid,
            job_number="BAD-001",
            work_date=self.week_start,
        )
        second = self.make_entry(
            second_sheet,
            job=None,
            job_number="bad-001",
            work_date=self.week_start + timedelta(days=8),
        )
        return invalid, first, second

    def test_non_management_user_cannot_open_cleanup(self):
        self.login(self.manager)
        response = self.client.get(reverse("invalid_job_cleanup"))
        self.assertRedirects(response, reverse("job_list"))

    def test_cleanup_lists_counts_and_date_range(self):
        invalid, first, second = self.make_invalid_job_with_entries()
        self.login(self.management)

        response = self.client.get(reverse("invalid_job_cleanup"))

        row = response.context["invalid_jobs"][0]
        self.assertEqual(row["job"], invalid)
        self.assertEqual(row["entry_count"], 2)
        self.assertEqual(row["first_date"], first.work_date)
        self.assertEqual(row["last_date"], second.work_date)
        self.assertIn(self.valid_job, list(response.context["valid_jobs"]))

    def test_cleanup_apply_requires_post(self):
        invalid, _first, _second = self.make_invalid_job_with_entries()
        self.login(self.management)

        response = self.client.get(reverse("invalid_job_cleanup_apply", args=[invalid.pk]))

        self.assertTrue(Job.objects.filter(pk=invalid.pk).exists())
        self.assertRedirects(response, reverse("invalid_job_cleanup"))

    def test_clear_action_unlinks_entries_and_deletes_invalid_job(self):
        invalid, first, second = self.make_invalid_job_with_entries()
        self.login(self.management)

        response = self.client.post(
            reverse("invalid_job_cleanup_apply", args=[invalid.pk]),
            {"action": "clear"},
        )

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(Job.objects.filter(pk=invalid.pk).exists())
        self.assertIsNone(first.job)
        self.assertEqual(first.job_number, "")
        self.assertIsNone(second.job)
        self.assertEqual(second.job_number, "")
        self.assertRedirects(response, reverse("invalid_job_cleanup"))

    def test_reassign_action_updates_entries_and_deletes_invalid_job(self):
        invalid, first, second = self.make_invalid_job_with_entries()
        self.login(self.management)

        response = self.client.post(
            reverse("invalid_job_cleanup_apply", args=[invalid.pk]),
            {"action": "reassign", "replacement_job_number": "26001"},
        )

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(Job.objects.filter(pk=invalid.pk).exists())
        self.assertEqual(first.job, self.valid_job)
        self.assertEqual(first.job_number, "26001")
        self.assertEqual(second.job, self.valid_job)
        self.assertRedirects(response, reverse("invalid_job_cleanup"))

    def test_reassign_rejects_invalid_replacement(self):
        invalid, _first, _second = self.make_invalid_job_with_entries()
        self.login(self.management)

        response = self.client.post(
            reverse("invalid_job_cleanup_apply", args=[invalid.pk]),
            {"action": "reassign", "replacement_job_number": "MISSING"},
        )

        self.assertTrue(Job.objects.filter(pk=invalid.pk).exists())
        self.assertRedirects(response, reverse("invalid_job_cleanup"))

    def test_missing_action_keeps_invalid_job(self):
        invalid, _first, _second = self.make_invalid_job_with_entries()
        self.login(self.management)

        response = self.client.post(reverse("invalid_job_cleanup_apply", args=[invalid.pk]), {})

        self.assertTrue(Job.objects.filter(pk=invalid.pk).exists())
        self.assertRedirects(response, reverse("invalid_job_cleanup"))

    def test_apply_rejects_job_with_nonblank_description(self):
        self.login(self.management)
        response = self.client.post(
            reverse("invalid_job_cleanup_apply", args=[self.valid_job.pk]),
            {"action": "clear"},
        )
        self.assertEqual(response.status_code, 404)


class TimesheetUploadViewTests(ManagementWorkflowBase):
    def setUp(self):
        super().setUp()
        self.media_dir = TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.media_dir.cleanup()
        super().tearDown()

    def test_upload_get_renders_form(self):
        self.login(self.employee)
        response = self.client.get(reverse("timesheet_upload"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)

    @patch("timesheets.views.find_invalid_time_entry_job_numbers")
    def test_upload_with_invalid_jobs_redirects_to_corrections(self, find_invalid):
        find_invalid.return_value = {"BAD": {"count": 1, "descriptions": ["Bad row"]}}
        self.login(self.employee)

        response = self.client.post(
            reverse("timesheet_upload"),
            {"uploaded_file": SimpleUploadedFile("sheet.xlsx", b"xlsx")},
        )

        upload = TimesheetImport.objects.get(employee=self.employee)
        self.assertEqual(upload.status, "pending")
        self.assertEqual(upload.message, "Import needs job number corrections.")
        self.assertRedirects(
            response,
            reverse("timesheet_upload_job_corrections", args=[upload.pk]),
        )

    @patch("timesheets.views.import_timesheet_upload")
    @patch("timesheets.views.find_invalid_time_entry_job_numbers", return_value={})
    def test_upload_success_redirects_to_imported_timesheet(self, _find_invalid, import_upload):
        timesheet = self.make_timesheet()
        import_upload.return_value = timesheet
        self.login(self.employee)

        response = self.client.post(
            reverse("timesheet_upload"),
            {"uploaded_file": SimpleUploadedFile("sheet.xlsx", b"xlsx")},
        )

        self.assertRedirects(response, timesheet.get_absolute_url())

    @patch("timesheets.views.import_timesheet_upload", side_effect=ValueError("broken workbook"))
    @patch("timesheets.views.find_invalid_time_entry_job_numbers", return_value={})
    def test_upload_import_failure_marks_upload_failed(self, _find_invalid, _import_upload):
        self.login(self.employee)

        response = self.client.post(
            reverse("timesheet_upload"),
            {"uploaded_file": SimpleUploadedFile("sheet.xlsx", b"xlsx")},
        )

        upload = TimesheetImport.objects.get(employee=self.employee)
        self.assertEqual(upload.status, "failed")
        self.assertEqual(upload.message, "broken workbook")
        self.assertRedirects(response, reverse("timesheet_upload"))

    @patch("timesheets.views.find_invalid_time_entry_job_numbers", return_value={})
    def test_correction_page_without_invalid_jobs_continues_import(self, _find_invalid):
        upload = self.make_upload()
        timesheet = self.make_timesheet()
        self.login(self.employee)

        with patch("timesheets.views.import_timesheet_upload", return_value=timesheet) as import_upload:
            response = self.client.get(
                reverse("timesheet_upload_job_corrections", args=[upload.pk])
            )

        import_upload.assert_called_once_with(upload)
        self.assertRedirects(response, timesheet.get_absolute_url())

    @patch("timesheets.views.find_invalid_time_entry_job_numbers")
    def test_correction_page_is_owner_only(self, find_invalid):
        find_invalid.return_value = {"BAD": {"count": 1, "descriptions": []}}
        upload = self.make_upload(employee=self.other_employee)
        self.login(self.employee)

        response = self.client.get(
            reverse("timesheet_upload_job_corrections", args=[upload.pk])
        )

        self.assertEqual(response.status_code, 404)

    @patch("timesheets.views.find_invalid_time_entry_job_numbers")
    def test_correction_get_sorts_invalid_items(self, find_invalid):
        find_invalid.return_value = {
            "ZZZ": {"count": 1, "descriptions": ["Z"]},
            "AAA": {"count": 2, "descriptions": ["A"]},
        }
        upload = self.make_upload()
        self.login(self.employee)

        response = self.client.get(
            reverse("timesheet_upload_job_corrections", args=[upload.pk])
        )

        self.assertEqual(
            [item["job_number"] for item in response.context["invalid_items"]],
            ["AAA", "ZZZ"],
        )

    @patch("timesheets.views.find_invalid_time_entry_job_numbers")
    def test_correction_post_requires_every_correction(self, find_invalid):
        find_invalid.return_value = {"BAD": {"count": 1, "descriptions": []}}
        upload = self.make_upload()
        self.login(self.employee)

        response = self.client.post(
            reverse("timesheet_upload_job_corrections", args=[upload.pk]),
            {},
        )

        self.assertEqual(response.status_code, 200)

    @patch("timesheets.views.find_invalid_time_entry_job_numbers")
    def test_correction_post_rejects_unavailable_replacement(self, find_invalid):
        find_invalid.return_value = {"BAD": {"count": 1, "descriptions": []}}
        upload = self.make_upload()
        self.login(self.employee)

        response = self.client.post(
            reverse("timesheet_upload_job_corrections", args=[upload.pk]),
            {"correction_1": "MISSING"},
        )

        self.assertEqual(response.status_code, 200)

    @patch("timesheets.views.find_invalid_time_entry_job_numbers")
    def test_valid_corrections_are_passed_to_importer(self, find_invalid):
        find_invalid.return_value = {
            "BAD1": {"count": 1, "descriptions": []},
            "BAD2": {"count": 1, "descriptions": []},
        }
        upload = self.make_upload()
        timesheet = self.make_timesheet()
        self.login(self.employee)

        with patch("timesheets.views.import_timesheet_upload", return_value=timesheet) as import_upload:
            response = self.client.post(
                reverse("timesheet_upload_job_corrections", args=[upload.pk]),
                {"correction_1": "26001", "correction_2": "__CLEAR__"},
            )

        import_upload.assert_called_once_with(
            upload,
            job_corrections={"BAD1": "26001", "BAD2": ""},
        )
        self.assertRedirects(response, timesheet.get_absolute_url())

    @patch("timesheets.views.find_invalid_time_entry_job_numbers")
    def test_correction_import_failure_marks_upload_failed(self, find_invalid):
        find_invalid.return_value = {"BAD": {"count": 1, "descriptions": []}}
        upload = self.make_upload()
        self.login(self.employee)

        with patch("timesheets.views.import_timesheet_upload", side_effect=ValueError("still bad")):
            response = self.client.post(
                reverse("timesheet_upload_job_corrections", args=[upload.pk]),
                {"correction_1": "26001"},
            )

        upload.refresh_from_db()
        self.assertEqual(upload.status, "failed")
        self.assertEqual(upload.message, "still bad")
        self.assertRedirects(response, reverse("timesheet_upload"))


class ArtifactIntermediatePageTests(ManagementWorkflowBase):
    def setUp(self):
        super().setUp()
        self.media_dir = TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.media_dir.cleanup()
        super().tearDown()

    def make_artifact(self, *, employee=None):
        timesheet = self.make_timesheet(employee=employee or self.employee)
        return TimesheetSubmissionArtifact.objects.create(
            timesheet=timesheet,
            file=SimpleUploadedFile("artifact.pdf", b"%PDF-test"),
            file_type=TimesheetSubmissionArtifact.FileType.PDF,
            export_format=Timesheet.ExportFormat.PDF,
            created_by=timesheet.employee,
        )

    def test_owner_can_open_both_intermediate_pages(self):
        artifact = self.make_artifact()
        self.login(self.employee)

        for name in ["timesheet_download_ready", "timesheet_submitted_download"]:
            with self.subTest(name=name):
                response = self.client.get(reverse(name, args=[artifact.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["artifact"], artifact)
                self.assertEqual(response.context["timesheet"], artifact.timesheet)

    def test_management_can_open_other_users_intermediate_pages(self):
        artifact = self.make_artifact(employee=self.other_employee)
        self.login(self.management)

        for name in ["timesheet_download_ready", "timesheet_submitted_download"]:
            with self.subTest(name=name):
                self.assertEqual(
                    self.client.get(reverse(name, args=[artifact.pk])).status_code,
                    200,
                )

    def test_regular_user_cannot_open_other_users_intermediate_pages(self):
        artifact = self.make_artifact(employee=self.other_employee)
        self.login(self.employee)

        for name in ["timesheet_download_ready", "timesheet_submitted_download"]:
            with self.subTest(name=name):
                self.assertEqual(
                    self.client.get(reverse(name, args=[artifact.pk])).status_code,
                    404,
                )

    def test_missing_artifact_returns_404_on_all_artifact_pages(self):
        self.login(self.management)

        for name in [
            "timesheet_download_ready",
            "timesheet_submitted_download",
            "timesheet_artifact_download",
        ]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name, args=[999999])).status_code, 404)
