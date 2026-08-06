from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from .base import AppTestCase

from accounts.models import EmployeeProfile
from timesheets.models import TimeEntry, Timesheet, TimesheetReopenRequest


User = get_user_model()


class TimesheetViewTestBase(AppTestCase):
    week_start = date(2026, 7, 26)

    @classmethod
    def setUpTestData(cls):
        cls.employee = User.objects.create_user(
            username="employee",
            password="test-password",
            first_name="Test",
            last_name="Employee",
            email="employee@gotoccs.com",
        )
        cls.other_employee = User.objects.create_user(
            username="other",
            password="test-password",
            first_name="Other",
            last_name="Employee",
            email="other@gotoccs.com",
        )
        cls.project_manager = User.objects.create_user(
            username="manager",
            password="test-password",
            first_name="Project",
            last_name="Manager",
            email="manager@gotoccs.com",
        )
        cls.management_user = User.objects.create_user(
            username="management",
            password="test-password",
            first_name="Management",
            last_name="User",
            email="management@gotoccs.com",
        )

        project_managers, _ = Group.objects.get_or_create(
            name="ProjectManagers"
        )
        
        management_staff, _ = Group.objects.get_or_create(
            name="Management Staff"
        )

        cls.project_manager.groups.add(project_managers)
        cls.management_user.groups.add(management_staff)

        EmployeeProfile.objects.create(
            user=cls.employee,
            supervisor=cls.project_manager,
        )
        EmployeeProfile.objects.create(user=cls.other_employee)
        EmployeeProfile.objects.create(user=cls.project_manager)
        EmployeeProfile.objects.create(user=cls.management_user)

    def make_timesheet(self, employee=None, status=Timesheet.Status.DRAFT, with_entry=False, week_start=None):
        timesheet = Timesheet.objects.create(
            employee=employee or self.employee,
            week_start=week_start or self.week_start,
            status=status,
        )
        if with_entry:
            TimeEntry.objects.create(
                timesheet=timesheet,
                work_date=timesheet.week_start,
                row_order=1,
                job_number="26001",
                regular_hours=8,
                description="Test work",
            )
        return timesheet


class AuthenticationAndOwnershipTests(TimesheetViewTestBase):
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("timesheet_list"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('timesheet_list')}")

    def test_employee_can_view_own_timesheet(self):
        timesheet = self.make_timesheet()
        self.client.force_login(self.employee)

        response = self.client.get(reverse("timesheet_detail", args=[timesheet.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["timesheet"], timesheet)

    def test_employee_cannot_view_another_employees_timesheet(self):
        timesheet = self.make_timesheet(employee=self.other_employee)
        self.client.force_login(self.employee)

        response = self.client.get(reverse("timesheet_detail", args=[timesheet.pk]))

        self.assertEqual(response.status_code, 404)

    def test_assigned_project_manager_can_view_employee_timesheet(self):
        timesheet = self.make_timesheet()
        self.client.force_login(self.project_manager)

        response = self.client.get(reverse("timesheet_detail", args=[timesheet.pk]))

        self.assertEqual(response.status_code, 200)

    def test_management_staff_can_view_any_timesheet(self):
        timesheet = self.make_timesheet(employee=self.other_employee)
        self.client.force_login(self.management_user)

        response = self.client.get(reverse("timesheet_detail", args=[timesheet.pk]))

        self.assertEqual(response.status_code, 200)


class TimesheetCreateTests(TimesheetViewTestBase):
    def test_create_timesheet_requires_sunday(self):
        self.client.force_login(self.employee)

        response = self.client.post(
            reverse("timesheet_create"),
            {"week_start": "2026-07-27", "entries_per_day": 5},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please choose a Sunday")
        self.assertFalse(Timesheet.objects.filter(employee=self.employee).exists())

    def test_create_timesheet_creates_draft_and_redirects_to_edit(self):
        self.client.force_login(self.employee)

        response = self.client.post(
            reverse("timesheet_create"),
            {"week_start": self.week_start.isoformat(), "entries_per_day": 7},
        )

        timesheet = Timesheet.objects.get(employee=self.employee, week_start=self.week_start)
        self.assertEqual(timesheet.status, Timesheet.Status.DRAFT)
        self.assertEqual(timesheet.entries_per_day, 7)
        self.assertRedirects(response, reverse("timesheet_edit", args=[timesheet.pk]))

    def test_create_existing_week_opens_existing_timesheet(self):
        timesheet = self.make_timesheet()
        self.client.force_login(self.employee)

        response = self.client.post(
            reverse("timesheet_create"),
            {"week_start": self.week_start.isoformat(), "entries_per_day": 10},
        )

        self.assertEqual(Timesheet.objects.filter(employee=self.employee, week_start=self.week_start).count(), 1)
        self.assertRedirects(response, reverse("timesheet_edit", args=[timesheet.pk]))


class TimesheetSubmissionTests(TimesheetViewTestBase):
    @patch("timesheets.views.send_timesheet_submitted_supervisor_email")
    def test_owner_can_submit_nonempty_draft(self, send_email):
        timesheet = self.make_timesheet(with_entry=True)
        self.client.force_login(self.employee)

        response = self.client.post(reverse("timesheet_submit", args=[timesheet.pk]))

        timesheet.refresh_from_db()
        self.assertEqual(timesheet.status, Timesheet.Status.SUBMITTED)
        self.assertEqual(timesheet.submitted_by, self.employee)
        self.assertIsNotNone(timesheet.submitted_at)
        send_email.assert_called_once()
        self.assertRedirects(response, reverse("timesheet_submitted", args=[timesheet.pk]))

    @patch("timesheets.views.send_timesheet_submitted_supervisor_email")
    def test_empty_timesheet_remains_draft(self, send_email):
        timesheet = self.make_timesheet()
        self.client.force_login(self.employee)

        response = self.client.post(reverse("timesheet_submit", args=[timesheet.pk]))

        timesheet.refresh_from_db()
        self.assertEqual(timesheet.status, Timesheet.Status.DRAFT)
        send_email.assert_not_called()
        self.assertRedirects(response, reverse("timesheet_detail", args=[timesheet.pk]))

    def test_user_cannot_submit_another_employees_timesheet(self):
        timesheet = self.make_timesheet(employee=self.other_employee, with_entry=True)
        self.client.force_login(self.employee)

        response = self.client.post(reverse("timesheet_submit", args=[timesheet.pk]))

        self.assertEqual(response.status_code, 404)
        timesheet.refresh_from_db()
        self.assertEqual(timesheet.status, Timesheet.Status.DRAFT)


class TimesheetApprovalTests(TimesheetViewTestBase):
    def test_project_manager_approval_list_only_contains_direct_reports(self):
        direct_report_sheet = self.make_timesheet(status=Timesheet.Status.SUBMITTED)
        unrelated_sheet = self.make_timesheet(
            employee=self.other_employee,
            status=Timesheet.Status.SUBMITTED,
        )
        self.client.force_login(self.project_manager)

        response = self.client.get(reverse("timesheet_approvals"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(direct_report_sheet, response.context["timesheets"])
        self.assertNotIn(unrelated_sheet, response.context["timesheets"])

    @patch("timesheets.views.send_employee_timesheet_approved_email")
    @patch("timesheets.views.send_timesheet_approved_email")
    def test_assigned_project_manager_can_approve_submitted_timesheet(self, send_admin_email, send_employee_email):
        timesheet = self.make_timesheet(status=Timesheet.Status.SUBMITTED)
        self.client.force_login(self.project_manager)

        response = self.client.post(reverse("timesheet_approve", args=[timesheet.pk]))

        timesheet.refresh_from_db()
        self.assertEqual(timesheet.status, Timesheet.Status.APPROVED)
        self.assertEqual(timesheet.approved_by, self.project_manager)
        send_admin_email.assert_called_once()
        send_employee_email.assert_called_once()
        self.assertRedirects(response, reverse("timesheet_approvals"))

    def test_unassigned_project_manager_cannot_approve_timesheet(self):
        timesheet = self.make_timesheet(
            employee=self.other_employee,
            status=Timesheet.Status.SUBMITTED,
        )
        self.client.force_login(self.project_manager)

        response = self.client.post(
            reverse("timesheet_approve", args=[timesheet.pk])
        )

        timesheet.refresh_from_db()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(timesheet.status, Timesheet.Status.SUBMITTED)

    @patch("timesheets.views.send_employee_timesheet_rejected_email")
    def test_assigned_project_manager_can_reject_with_reason(self, send_email):
        timesheet = self.make_timesheet(status=Timesheet.Status.SUBMITTED)
        self.client.force_login(self.project_manager)

        response = self.client.post(
            reverse("timesheet_reject", args=[timesheet.pk]),
            {"reason": "Please correct the job number."},
        )

        timesheet.refresh_from_db()
        self.assertEqual(timesheet.status, Timesheet.Status.REJECTED)
        self.assertEqual(timesheet.rejected_by, self.project_manager)
        self.assertEqual(timesheet.rejection_reason, "Please correct the job number.")
        send_email.assert_called_once()
        self.assertRedirects(response, reverse("timesheet_approvals"))

    def test_management_staff_can_mark_approved_timesheet_invoiced(self):
        timesheet = self.make_timesheet(status=Timesheet.Status.APPROVED)
        self.client.force_login(self.management_user)

        response = self.client.post(reverse("timesheet_mark_invoiced", args=[timesheet.pk]))

        timesheet.refresh_from_db()
        self.assertEqual(timesheet.status, Timesheet.Status.INVOICED)
        self.assertEqual(timesheet.invoiced_by, self.management_user)
        self.assertRedirects(response, reverse("timesheet_detail", args=[timesheet.pk]))


class ReopenRequestTests(TimesheetViewTestBase):
    @patch("timesheets.views.send_timesheet_reopen_request_email")
    def test_employee_request_is_pending_when_supervisor_is_assigned(self, send_email):
        timesheet = self.make_timesheet(status=Timesheet.Status.APPROVED)
        self.client.force_login(self.employee)

        response = self.client.post(
            reverse("timesheet_reopen_request", args=[timesheet.pk]),
            {"reason": "I need to correct Thursday.", "priority": "medium"},
        )

        reopen_request = TimesheetReopenRequest.objects.get(timesheet=timesheet)
        self.assertEqual(reopen_request.status, "pending")
        self.assertEqual(reopen_request.supervisor, self.project_manager)
        self.assertEqual(reopen_request.requested_by, self.employee)
        send_email.assert_called_once_with(reopen_request)
        self.assertRedirects(response, reverse("timesheet_detail", args=[timesheet.pk]))

    @patch("timesheets.views.send_reopened_admin_notification")
    @patch("timesheets.views.send_employee_reopen_approved_email")
    def test_request_without_supervisor_is_automatically_approved(self, send_employee_email, send_admin_email):
        timesheet = self.make_timesheet(employee=self.other_employee, status=Timesheet.Status.APPROVED)
        self.client.force_login(self.other_employee)

        response = self.client.post(
            reverse("timesheet_reopen_request", args=[timesheet.pk]),
            {"reason": "Correction needed.", "priority": "low"},
        )

        reopen_request = TimesheetReopenRequest.objects.get(timesheet=timesheet)
        timesheet.refresh_from_db()
        self.assertEqual(reopen_request.status, "approved")
        self.assertEqual(timesheet.status, Timesheet.Status.REOPENED)
        send_employee_email.assert_called_once()
        send_admin_email.assert_called_once()
        self.assertRedirects(response, reverse("timesheet_detail", args=[timesheet.pk]))

    def test_management_staff_can_open_reopen_request_list(self):
        self.client.force_login(self.management_user)

        response = self.client.get(reverse("reopen_request_list"))

        self.assertEqual(response.status_code, 200)

    @patch("timesheets.views.send_reopened_admin_notification")
    @patch("timesheets.views.send_employee_reopen_approved_email")
    def test_management_staff_can_approve_reopen_request(self, send_employee_email, send_admin_email):
        timesheet = self.make_timesheet(status=Timesheet.Status.APPROVED)
        reopen_request = TimesheetReopenRequest.objects.create(
            timesheet=timesheet,
            requested_by=self.employee,
            supervisor=self.project_manager,
            reason="Correction needed.",
        )
        self.client.force_login(self.management_user)

        response = self.client.post(
            reverse("reopen_request_approve", args=[reopen_request.pk]),
            {"decision_notes": "Approved."},
        )

        reopen_request.refresh_from_db()
        timesheet.refresh_from_db()
        self.assertEqual(reopen_request.status, "approved")
        self.assertEqual(reopen_request.decided_by, self.management_user)
        self.assertEqual(timesheet.status, Timesheet.Status.REOPENED)
        self.assertRedirects(response, reverse("reopen_request_list"))
