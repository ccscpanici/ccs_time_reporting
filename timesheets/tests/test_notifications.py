from .base import AppTestCase
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.mail import get_connection
from django.test import override_settings
from django.utils import timezone

from accounts.models import EmployeeProfile
from timesheets.models import (
    ApprovalNotificationRecipient,
    EmailConfiguration,
    TimeEntry,
    Timesheet,
    TimesheetReopenRequest,
    TimesheetSubmissionArtifact,
)
from timesheets.services import notifications


User = get_user_model()


class NotificationTestBase(AppTestCase):
    week_start = date(2026, 8, 2)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media = TemporaryDirectory()
        cls._settings = override_settings(
            MEDIA_ROOT=cls._media.name,
            SITE_BASE_URL="https://tests.example.com/",
        )
        cls._settings.enable()

    @classmethod
    def tearDownClass(cls):
        cls._settings.disable()
        cls._media.cleanup()
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.employee = User.objects.create_user(
            username="employee",
            first_name="Test",
            last_name="Employee",
            email="employee@example.com",
        )
        cls.supervisor = User.objects.create_user(
            username="supervisor",
            first_name="Sue",
            last_name="Supervisor",
            email="supervisor@example.com",
        )
        cls.manager = User.objects.create_user(
            username="manager",
            first_name="Manny",
            last_name="Manager",
            email="manager@example.com",
        )
        EmployeeProfile.objects.create(user=cls.employee, supervisor=cls.supervisor)
        EmployeeProfile.objects.create(user=cls.supervisor)
        EmployeeProfile.objects.create(user=cls.manager)

    def setUp(self):
        mail.outbox = []
        self.config = EmailConfiguration.objects.create(
            name="Test SMTP",
            from_email="timetrack@example.com",
            reply_to_email="reply@example.com",
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="user",
            smtp_password="secret",
            use_tls=True,
            active=True,
            test_recipient="test-recipient@example.com",
        )
        self.backend_patcher = patch(
            "timesheets.services.notifications._smtp_backend",
            return_value=get_connection("django.core.mail.backends.locmem.EmailBackend"),
        )
        self.backend_patcher.start()
        self.addCleanup(self.backend_patcher.stop)

    def make_timesheet(self, **overrides):
        values = {
            "employee": self.employee,
            "week_start": self.week_start,
            "status": Timesheet.Status.APPROVED,
            "approved_by": self.manager,
            "approved_at": timezone.now(),
        }
        values.update(overrides)
        return Timesheet.objects.create(**values)

    def make_reopen_request(self, **overrides):
        values = {
            "timesheet": self.make_timesheet(),
            "requested_by": self.employee,
            "supervisor": self.supervisor,
            "reason": "Correct project hours.",
            "priority": TimesheetReopenRequest.Priority.HIGH,
        }
        values.update(overrides)
        return TimesheetReopenRequest.objects.create(**values)


class NotificationHelperTests(NotificationTestBase):
    def test_employee_initials_uses_full_name(self):
        self.assertEqual(notifications._employee_initials(self.employee), "TE")

    def test_employee_initials_falls_back_to_username(self):
        user = User.objects.create_user(username="xyuser")
        self.assertEqual(notifications._employee_initials(user), "XY")

    def test_timesheet_url_normalizes_trailing_slash(self):
        timesheet = self.make_timesheet()
        self.assertEqual(
            notifications._timesheet_url(timesheet),
            f"https://tests.example.com{timesheet.get_absolute_url()}",
        )

    def test_basic_email_ignores_blank_recipients(self):
        notifications._send_basic_email(
            config=self.config,
            subject="Hello",
            body="Body",
            to=["", None],
        )
        self.assertEqual(mail.outbox, [])

    def test_active_config_uses_latest_active_configuration(self):
        newer = EmailConfiguration.objects.create(
            name="Newer",
            from_email="newer@example.com",
            smtp_host="smtp.example.com",
            active=True,
        )
        self.assertEqual(EmailConfiguration.active_config(), newer)


class BasicNotificationTests(NotificationTestBase):
    def test_send_test_email_requires_recipient(self):
        self.config.test_recipient = ""
        self.config.save(update_fields=["test_recipient"])
        with self.assertRaisesMessage(ValueError, "Test recipient is required"):
            notifications.send_test_email(self.config)

    def test_send_test_email_uses_configured_addresses(self):
        notifications.send_test_email(self.config)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "CCS Time Reporting - Test Email")
        self.assertEqual(message.to, ["test-recipient@example.com"])
        self.assertEqual(message.from_email, "timetrack@example.com")
        self.assertEqual(message.reply_to, ["reply@example.com"])
        self.assertIn("smtp.example.com", message.body)

    def test_employee_approval_email_contains_approver_and_link(self):
        timesheet = self.make_timesheet()
        notifications.send_employee_timesheet_approved_email(timesheet, self.manager)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["employee@example.com"])
        self.assertIn("Timesheet Approved", message.subject)
        self.assertIn("Manny Manager", message.body)
        self.assertIn("https://tests.example.com", message.body)

    def test_employee_rejection_email_includes_reason(self):
        timesheet = self.make_timesheet(status=Timesheet.Status.REJECTED)
        notifications.send_employee_timesheet_rejected_email(
            timesheet,
            self.manager,
            "Use the correct job number.",
        )
        message = mail.outbox[0]
        self.assertEqual(message.to, ["employee@example.com"])
        self.assertIn("Timesheet Rejected", message.subject)
        self.assertIn("Use the correct job number.", message.body)

    def test_submitted_email_goes_to_assigned_supervisor(self):
        timesheet = self.make_timesheet(status=Timesheet.Status.SUBMITTED)
        notifications.send_timesheet_submitted_supervisor_email(timesheet, self.employee)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["supervisor@example.com"])
        self.assertIn("Test Employee Timesheet", message.subject)
        self.assertIn("Submitted By: Test Employee", message.body)

    def test_reopened_admin_notification_uses_active_recipients_only(self):
        active = ApprovalNotificationRecipient.objects.create(email="active@example.com", active=True)
        ApprovalNotificationRecipient.objects.create(email="inactive@example.com", active=False)
        timesheet = self.make_timesheet(reopen_reason="Fix Wednesday.")
        notifications.send_reopened_admin_notification(timesheet, self.manager)
        message = mail.outbox[0]
        self.assertEqual(message.to, [active.email])
        self.assertIn("Fix Wednesday.", message.body)


class ReopenRequestNotificationTests(NotificationTestBase):
    def test_reopen_request_email_contains_priority_reason_and_review_link(self):
        request = self.make_reopen_request()
        notifications.send_timesheet_reopen_request_email(request)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["supervisor@example.com"])
        self.assertIn("Priority: High", message.body)
        self.assertIn("Correct project hours.", message.body)
        self.assertIn(f"/timesheets/reopen-requests/{request.pk}/", message.body)

    def test_reopen_approved_email_contains_decider_and_notes(self):
        request = self.make_reopen_request(
            status="approved",
            decided_by=self.manager,
            decision_notes="Approved for correction.",
        )
        notifications.send_employee_reopen_approved_email(request)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["employee@example.com"])
        self.assertIn("Reopen Request Approved", message.subject)
        self.assertIn("Manny Manager", message.body)
        self.assertIn("Approved for correction.", message.body)

    def test_reopen_rejected_email_uses_system_when_no_decider(self):
        request = self.make_reopen_request(
            status="denied",
            decided_by=None,
            decision_notes="Outside correction window.",
        )
        notifications.send_employee_reopen_rejected_email(request)
        message = mail.outbox[0]
        self.assertIn("Rejected By: System", message.body)
        self.assertIn("Outside correction window.", message.body)


class NotificationValidationTests(NotificationTestBase):
    def test_missing_active_email_configuration_raises(self):
        EmailConfiguration.objects.update(active=False)
        timesheet = self.make_timesheet()
        with self.assertRaisesMessage(ValueError, "No active email configuration"):
            notifications.send_employee_timesheet_approved_email(timesheet, self.manager)

    def test_employee_email_is_required(self):
        self.employee.email = ""
        self.employee.save(update_fields=["email"])
        timesheet = self.make_timesheet()
        with self.assertRaisesMessage(ValueError, "Employee does not have an email address"):
            notifications.send_employee_timesheet_approved_email(timesheet, self.manager)

    def test_supervisor_assignment_is_required_for_submission_email(self):
        self.employee.employee_profile.supervisor = None
        self.employee.employee_profile.save(update_fields=["supervisor"])
        timesheet = self.make_timesheet(status=Timesheet.Status.SUBMITTED)
        with self.assertRaisesMessage(ValueError, "supervisor assigned"):
            notifications.send_timesheet_submitted_supervisor_email(timesheet, self.employee)

    def test_supervisor_email_is_required_for_reopen_request(self):
        self.supervisor.email = ""
        self.supervisor.save(update_fields=["email"])
        request = self.make_reopen_request()
        with self.assertRaisesMessage(ValueError, "Supervisor does not have an email address"):
            notifications.send_timesheet_reopen_request_email(request)

    def test_admin_recipient_is_required_for_reopened_notification(self):
        timesheet = self.make_timesheet()
        with self.assertRaisesMessage(ValueError, "No active approval notification recipients"):
            notifications.send_reopened_admin_notification(timesheet, self.manager)


class ApprovedTimesheetAttachmentTests(NotificationTestBase):
    def test_approved_email_generates_artifacts_and_three_attachments(self):
        ApprovalNotificationRecipient.objects.create(email="accounting@example.com")
        timesheet = self.make_timesheet()

        workdir = Path(self._media.name)
        excel_path = workdir / "source.xlsx"
        pdf_path = workdir / "source.pdf"
        excel_path.write_bytes(b"xlsx-data")
        pdf_path.write_bytes(b"%PDF-test-data")

        with (
            patch("timesheets.services.notifications.build_timesheet_excel", return_value=excel_path),
            patch("timesheets.services.notifications.build_timesheet_pdf", return_value=pdf_path),
            patch("timesheets.services.notifications.build_receipts_pdf_bytes", return_value=b"%PDF-receipts"),
            patch("timesheets.services.notifications.receipts_pdf_filename", return_value="receipts.pdf"),
        ):
            notifications.send_timesheet_approved_email(timesheet, self.manager)

        message = mail.outbox[0]
        self.assertEqual(message.to, ["accounting@example.com"])
        self.assertEqual(len(message.attachments), 3)
        self.assertEqual(
            [attachment[0] for attachment in message.attachments],
            ["TE_20260802.xlsx", "TE_20260802_timesheet.pdf", "receipts.pdf"],
        )
        self.assertEqual(TimesheetSubmissionArtifact.objects.filter(timesheet=timesheet).count(), 3)
        self.assertTrue(
            TimesheetSubmissionArtifact.objects.filter(
                timesheet=timesheet,
                submitted=True,
                created_by=self.manager,
            ).exists()
        )

    def test_approved_email_skips_excel_when_timesheet_cannot_export_excel(self):
        ApprovalNotificationRecipient.objects.create(email="accounting@example.com")
        timesheet = self.make_timesheet(template_entries_per_day=5)
        for row_order in range(1, 7):
            TimeEntry.objects.create(
                timesheet=timesheet,
                work_date=timesheet.week_start,
                row_order=row_order,
                description=f"Overflow row {row_order}",
            )
        workdir = Path(self._media.name)
        pdf_path = workdir / "source.pdf"
        pdf_path.write_bytes(b"%PDF-test-data")

        with (
            patch("timesheets.services.notifications.build_timesheet_excel") as build_excel,
            patch("timesheets.services.notifications.build_timesheet_pdf", return_value=pdf_path),
            patch("timesheets.services.notifications.build_receipts_pdf_bytes", return_value=b"%PDF-receipts"),
            patch("timesheets.services.notifications.receipts_pdf_filename", return_value="receipts.pdf"),
        ):
            notifications.send_timesheet_approved_email(timesheet, self.manager)

        build_excel.assert_not_called()
        self.assertEqual(len(mail.outbox[0].attachments), 2)
        self.assertEqual(TimesheetSubmissionArtifact.objects.filter(timesheet=timesheet).count(), 2)

    def test_approved_email_requires_active_recipient(self):
        ApprovalNotificationRecipient.objects.create(email="inactive@example.com", active=False)
        timesheet = self.make_timesheet()
        with self.assertRaisesMessage(ValueError, "No active approval notification recipients"):
            notifications.send_timesheet_approved_email(timesheet, self.manager)
