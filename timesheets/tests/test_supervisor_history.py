from datetime import date
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import EmployeeProfile
from timesheets.models import Timesheet
from timesheets.permissions import can_view_timesheet


class SupervisorHistoryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.supervisor = User.objects.create_user(username="history_supervisor", password="pass")
        self.other = User.objects.create_user(username="history_other", password="pass")
        self.employee = User.objects.create_user(username="history_employee", password="pass")
        Group.objects.get_or_create(name="ProjectManagers")[0].user_set.add(self.supervisor)
        EmployeeProfile.objects.update_or_create(user=self.employee, defaults={"supervisor": self.supervisor})
        self.draft = Timesheet.objects.create(employee=self.employee, week_start=date(2026, 10, 4))
        self.submitted = Timesheet.objects.create(employee=self.employee, week_start=date(2026, 10, 11), status=Timesheet.Status.APPROVED, submitted_at=timezone.now())
        self.reopened = Timesheet.objects.create(employee=self.employee, week_start=date(2026, 10, 18), status=Timesheet.Status.REOPENED, submitted_at=timezone.now())

    def test_assigned_supervisor_draft_excluded_from_history_and_review(self):
        # Preserve legacy detail permissions; new supervisor pages exclude unsubmitted drafts.
        self.assertTrue(can_view_timesheet(self.supervisor, self.draft))
        self.client.force_login(self.supervisor)
        self.assertEqual(self.client.get(reverse("timesheet_detail", args=[self.draft.pk])).status_code, 200)
        history = self.client.get(reverse("supervisor_timesheet_history"))
        self.assertEqual(history.status_code, 200)
        self.assertNotIn(self.draft.pk, [sheet.pk for sheet in history.context["timesheets"]])
        self.assertEqual(self.client.get(reverse("timesheet_supervisor_review", args=[self.draft.pk])).status_code, 404)

    def test_supervisor_history_only_submitted(self):
        self.client.force_login(self.supervisor)
        response = self.client.get(reverse("supervisor_timesheet_history"))
        self.assertEqual(response.status_code, 200)
        ids = [sheet.pk for sheet in response.context["timesheets"]]
        self.assertIn(self.submitted.pk, ids)
        self.assertIn(self.reopened.pk, ids)
        self.assertNotIn(self.draft.pk, ids)

    def test_unrelated_user_cannot_view(self):
        self.assertFalse(can_view_timesheet(self.other, self.submitted))
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("supervisor_timesheet_history")).status_code, 404)
        self.assertEqual(self.client.get(reverse("timesheet_detail", args=[self.submitted.pk])).status_code, 404)

    def test_filter_status(self):
        self.client.force_login(self.supervisor)
        response = self.client.get(reverse("supervisor_timesheet_history"), {"status": "reopened"})
        self.assertEqual([ts.pk for ts in response.context["timesheets"]], [self.reopened.pk])

    def test_owner_can_still_view_draft(self):
        self.assertTrue(can_view_timesheet(self.employee, self.draft))

    def test_review_displays_employee_and_is_separate_from_owner_detail(self):
        self.employee.first_name = "Taylor"
        self.employee.last_name = "Example"
        self.employee.save(update_fields=["first_name", "last_name"])
        self.client.force_login(self.supervisor)
        response = self.client.get(reverse("timesheet_supervisor_review", args=[self.submitted.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "timesheets/supervisor_review.html")
        self.assertContains(response, "Taylor Example")
        self.assertContains(response, "Supervisor / Management Review")
        self.assertNotContains(response, 'href="' + reverse("timesheet_edit", args=[self.submitted.pk]) + '"')
        self.client.force_login(self.employee)
        owner = self.client.get(reverse("timesheet_detail", args=[self.submitted.pk]))
        self.assertEqual(owner.status_code, 200)
        self.assertTemplateUsed(owner, "timesheets/detail.html")

    def test_review_rejects_never_submitted_and_unrelated_users(self):
        self.client.force_login(self.supervisor)
        self.assertEqual(self.client.get(reverse("timesheet_supervisor_review", args=[self.draft.pk])).status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("timesheet_supervisor_review", args=[self.submitted.pk])).status_code, 404)

    def test_queue_and_history_link_to_supervisor_review(self):
        self.submitted.status = Timesheet.Status.SUBMITTED
        self.submitted.save(update_fields=["status"])
        self.client.force_login(self.supervisor)
        target = reverse("timesheet_supervisor_review", args=[self.submitted.pk])
        approvals = self.client.get(reverse("timesheet_approvals"))
        self.assertEqual(approvals.status_code, 200)
        self.assertContains(approvals, target)
        history = self.client.get(reverse("supervisor_timesheet_history"))
        self.assertEqual(history.status_code, 200)
        self.assertContains(history, target)
