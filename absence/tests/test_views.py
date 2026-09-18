from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import EmployeeProfile
from absence.models import AbsenceRequest, AbsenceRequestDay, PTOAccount, PTOAccountChange, PTOImport, PTOImportRow

User = get_user_model()


class AbsenceViewBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        pm_group, _ = Group.objects.get_or_create(name="ProjectManagers")
        management_group, _ = Group.objects.get_or_create(name="Management Staff")
        cls.manager = User.objects.create_user(username="manager", first_name="Mandy", last_name="Manager", password="test")
        cls.manager.groups.add(pm_group)
        cls.management = User.objects.create_user(username="management", first_name="Morgan", last_name="Management", password="test")
        cls.management.groups.add(management_group)
        cls.employee = User.objects.create_user(username="employee", first_name="Eddie", last_name="Employee", password="test")
        cls.other = User.objects.create_user(username="other", first_name="Other", last_name="Employee", password="test")
        EmployeeProfile.objects.create(user=cls.manager)
        EmployeeProfile.objects.create(user=cls.management)
        EmployeeProfile.objects.create(user=cls.employee, supervisor=cls.manager)
        EmployeeProfile.objects.create(user=cls.other)

    def make_request(self, **kwargs):
        defaults = {
            "employee": self.employee,
            "manager": self.manager,
            "absence_type": AbsenceRequest.AbsenceType.VACATION,
            "start_date": date(2026, 9, 21),
            "end_date": date(2026, 9, 25),
            "requested_minutes": 2400,
            "calendar_acknowledged": True,
        }
        defaults.update(kwargs)
        return AbsenceRequest.objects.create(**defaults)


class AbsenceRequestWorkflowTests(AbsenceViewBase):
    def test_employee_creates_draft(self):
        PTOAccount.objects.create(employee=self.employee, vacation_balance_minutes=6000)
        self.client.force_login(self.employee)
        response = self.client.post(reverse("absence_create"), {
            "absence_type": "vacation",
            "start_date": "2026-09-21",
            "end_date": "2026-09-25",
            "calendar_acknowledged": "on",
        })
        absence = AbsenceRequest.objects.get(employee=self.employee)
        self.assertEqual(absence.status, AbsenceRequest.Status.DRAFT)
        self.assertEqual(absence.requested_minutes, 2400)
        self.assertRedirects(response, reverse("absence_detail", args=[absence.pk]))

    def test_employee_can_create_partial_day_request(self):
        PTOAccount.objects.create(employee=self.employee, vacation_weeks_per_year=3)
        self.client.force_login(self.employee)
        response = self.client.post(reverse("absence_create"), {
            "absence_type": "vacation",
            "start_date": "2026-09-21",
            "end_date": "2026-09-22",
            "calendar_acknowledged": "on",
            "day_hours_2026-09-21": "4.00",
            "day_hours_2026-09-22": "8.00",
        })
        absence = AbsenceRequest.objects.get(employee=self.employee)
        self.assertEqual(absence.requested_minutes, 720)
        self.assertEqual(
            list(absence.days.values_list("work_date", "requested_minutes")),
            [(date(2026, 9, 21), 240), (date(2026, 9, 22), 480)],
        )
        self.assertRedirects(response, reverse("absence_detail", args=[absence.pk]))

    def test_project_manager_without_supervisor_defaults_to_self_on_submit(self):
        absence = AbsenceRequest.objects.create(
            employee=self.manager,
            absence_type=AbsenceRequest.AbsenceType.VACATION,
            start_date=date(2026, 11, 16),
            end_date=date(2026, 11, 16),
            requested_minutes=240,
            calendar_acknowledged=True,
            status=AbsenceRequest.Status.DRAFT,
        )
        AbsenceRequestDay.objects.create(
            request=absence,
            work_date=date(2026, 11, 16),
            requested_minutes=240,
        )
        self.client.force_login(self.manager)
        self.client.post(reverse("absence_submit", args=[absence.pk]))
        absence.refresh_from_db()
        self.assertEqual(absence.manager, self.manager)

    def test_submit_snapshots_manager_and_pto(self):
        PTOAccount.objects.create(
            employee=self.employee,
            vacation_weeks_per_year=3,
            vacation_balance_minutes=4800,
            sick_balance_minutes=1200,
            balance_as_of=date(2026, 9, 8),
        )
        absence = self.make_request(status=AbsenceRequest.Status.DRAFT, manager=None)
        self.client.force_login(self.employee)
        response = self.client.post(reverse("absence_submit", args=[absence.pk]))
        absence.refresh_from_db()
        self.assertEqual(absence.status, AbsenceRequest.Status.SUBMITTED)
        self.assertEqual(absence.manager, self.manager)
        self.assertEqual(absence.vacation_balance_snapshot_minutes, 7200)
        self.assertEqual(absence.vacation_used_snapshot_minutes, 0)
        self.assertEqual(absence.approved_vacation_pending_snapshot_minutes, 0)
        self.assertEqual(absence.sick_balance_snapshot_minutes, 1200)
        self.assertEqual(absence.projected_vacation_balance_minutes, 4800)
        self.assertIsNotNone(absence.submitted_at)
        self.assertRedirects(response, reverse("absence_detail", args=[absence.pk]))

    def test_sick_request_inside_two_weeks_is_not_late(self):
        today = timezone.localdate()
        absence = self.make_request(
            absence_type=AbsenceRequest.AbsenceType.SICK,
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=1),
            status=AbsenceRequest.Status.DRAFT,
            calendar_acknowledged=False,
        )
        self.client.force_login(self.employee)
        self.client.post(reverse("absence_submit", args=[absence.pk]))
        absence.refresh_from_db()
        self.assertFalse(absence.late_notice)

    @patch("absence.views.ensure_final_pdf")
    def test_assigned_manager_approves_normal_request_and_archives_pdf(self, ensure_pdf):
        absence = self.make_request(status=AbsenceRequest.Status.SUBMITTED)
        self.client.force_login(self.manager)
        response = self.client.post(reverse("absence_approve", args=[absence.pk]), {"notes": "Approved."})
        absence.refresh_from_db()
        self.assertEqual(absence.status, AbsenceRequest.Status.APPROVED)
        self.assertEqual(absence.supervisor_approved_by, self.manager)
        self.assertIsNotNone(absence.finalized_at)
        ensure_pdf.assert_called_once()
        self.assertRedirects(response, reverse("absence_detail", args=[absence.pk]))

    @patch("absence.views.ensure_final_pdf")
    def test_negative_balance_request_requires_management_exception_approval(self, ensure_pdf):
        absence = self.make_request(
            status=AbsenceRequest.Status.SUBMITTED,
            negative_balance_exception_required=True,
            negative_balance_acknowledged=True,
            unpaid_start_date=date(2026, 9, 28),
            unpaid_end_date=date(2026, 10, 2),
        )
        self.client.force_login(self.manager)
        self.client.post(reverse("absence_approve", args=[absence.pk]))
        absence.refresh_from_db()
        self.assertEqual(absence.status, AbsenceRequest.Status.PENDING_EXCEPTION)
        ensure_pdf.assert_not_called()

        self.client.force_login(self.management)
        self.client.post(reverse("absence_exception_approve", args=[absence.pk]))
        absence.refresh_from_db()
        self.assertEqual(absence.status, AbsenceRequest.Status.APPROVED)
        self.assertEqual(absence.exception_approved_by, self.management)
        ensure_pdf.assert_called_once()

    def test_employee_cannot_view_another_employees_request(self):
        absence = self.make_request(employee=self.other)
        self.client.force_login(self.employee)
        response = self.client.get(reverse("absence_detail", args=[absence.pk]))
        self.assertEqual(response.status_code, 404)


class PTOManagementViewTests(AbsenceViewBase):
    def test_supervisor_can_manually_update_direct_report_and_audit(self):
        account = PTOAccount.objects.create(employee=self.employee)
        self.client.force_login(self.manager)
        response = self.client.post(reverse("pto_balance_edit", args=[self.employee.pk]), {
            "vacation_weeks_per_year": "3.00",
            "vacation_accrual": "73:01",
            "vacation_used": "63:00",
            "sick_available": "-109:00",
            "sick_used": "17:30",
            "balance_as_of": "2026-09-08",
            "note": "Payroll report correction.",
        })
        account.refresh_from_db()
        self.assertEqual(account.vacation_balance_minutes, 4381)
        self.assertEqual(account.sick_balance_minutes, -6540)
        self.assertEqual(PTOAccountChange.objects.filter(pto_account=account, source=PTOAccountChange.Source.MANUAL).count(), 1)
        self.assertRedirects(response, reverse("pto_balance_list"))

    def test_supervisor_cannot_edit_unassigned_employee(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("pto_balance_edit", args=[self.other.pk]))
        self.assertEqual(response.status_code, 404)

    def test_pto_import_is_management_only(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse("pto_import_upload")).status_code, 403)
        self.client.force_login(self.management)
        self.assertEqual(self.client.get(reverse("pto_import_upload")).status_code, 200)

    def test_pto_import_preview_allows_partial_matches(self):
        pto_import = PTOImport.objects.create(
            source_file="absence/pto_imports/test.pdf",
            source_name="PTOList.pdf",
            report_date=date(2026, 9, 8),
            uploaded_by=self.management,
        )
        PTOImportRow.objects.create(
            pto_import=pto_import,
            row_number=1,
            employee_name="Employee, Eddie",
            employee=self.employee,
            match_status=PTOImportRow.MatchStatus.MATCHED,
            vacation_available_minutes=600,
            vacation_used_minutes=120,
        )
        PTOImportRow.objects.create(
            pto_import=pto_import,
            row_number=2,
            employee_name="Unknown, Person",
            match_status=PTOImportRow.MatchStatus.UNMATCHED,
        )

        self.client.force_login(self.management)
        response = self.client.get(reverse("pto_import_preview", args=[pto_import.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["matched_count"], 1)
        self.assertEqual(response.context["skipped_count"], 1)
        self.assertContains(response, "Apply 1 Matched Employee")
        self.assertContains(response, "will be skipped")
