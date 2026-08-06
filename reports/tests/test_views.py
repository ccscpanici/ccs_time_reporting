from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from timesheets.tests.base import AppTestCase
from django.utils import timezone

from timesheets.models import TimeEntry, Timesheet


User = get_user_model()


class ReportViewTestBase(AppTestCase):
    week_start = date(2026, 8, 2)

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
            last_name="Worker",
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
        cls.superuser = User.objects.create_superuser(
            username="admin",
            password="test-password",
            email="admin@gotoccs.com",
        )

        project_managers, _ = Group.objects.get_or_create(name="ProjectManagers")
        management_staff, _ = Group.objects.get_or_create(name="Management Staff")
        cls.project_manager.groups.add(project_managers)
        cls.management_user.groups.add(management_staff)

    def make_timesheet(
        self,
        *,
        employee=None,
        status=Timesheet.Status.APPROVED,
        week_start=None,
        deleted=False,
    ):
        return self.make_timesheet_record(
            employee=employee or self.employee,
            week_start=week_start or self.week_start,
            status=status,
            deleted_at=timezone.now() if deleted else None,
        )

    def make_entry(
        self,
        timesheet,
        *,
        day_offset=0,
        row_order=1,
        job_number="26001",
        regular="0.00",
        overtime="0.00",
        doubletime="0.00",
        description="Test work",
    ):
        return self.make_time_entry_record(
            timesheet=timesheet,
            work_date=timesheet.week_start + timedelta(days=day_offset),
            row_order=row_order,
            job_number=job_number,
            regular_hours=Decimal(regular),
            overtime_hours=Decimal(overtime),
            doubletime_hours=Decimal(doubletime),
            description=description,
        )


class ReportsDashboardTests(ReportViewTestBase):
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("reports_dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('reports_dashboard')}",
        )

    def test_authenticated_user_can_open_dashboard(self):
        self.client.force_login(self.employee)

        response = self.client.get(reverse("reports_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reports/dashboard.html")


class BillabilityReportTests(ReportViewTestBase):
    def test_regular_employee_cannot_open_company_billability_report(self):
        self.client.force_login(self.employee)

        response = self.client.get(reverse("billability_report"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_management_staff_can_open_report_without_running_it(self):
        self.client.force_login(self.management_user)

        response = self.client.get(reverse("billability_report"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["report_ran"])
        self.assertEqual(response.context["rows"], [])

    def test_report_calculates_billable_and_nonbillable_hours(self):
        timesheet = self.make_timesheet()
        self.make_entry(timesheet, row_order=1, job_number="26001", regular="6.00", overtime="2.00")
        self.make_entry(timesheet, row_order=2, job_number="", regular="2.00")
        self.client.force_login(self.management_user)

        response = self.client.get(reverse("billability_report"), {"run": "1"})

        employee_row = next(
            row for row in response.context["rows"] if row["employee"] == self.employee
        )
        self.assertEqual(employee_row["total_hours"], Decimal("10.00"))
        self.assertEqual(employee_row["billable_hours"], Decimal("8.00"))
        self.assertEqual(employee_row["non_billable_hours"], Decimal("2.00"))
        self.assertEqual(employee_row["billability"], Decimal("80.0"))

    def test_report_excludes_management_and_superusers(self):
        management_sheet = self.make_timesheet(employee=self.management_user)
        superuser_sheet = self.make_timesheet(employee=self.superuser)
        self.make_entry(management_sheet, regular="8.00")
        self.make_entry(superuser_sheet, regular="8.00")
        self.client.force_login(self.management_user)

        response = self.client.get(reverse("billability_report"), {"run": "1"})

        employees = {row["employee"] for row in response.context["rows"]}
        self.assertNotIn(self.management_user, employees)
        self.assertNotIn(self.superuser, employees)
        self.assertIn(self.employee, employees)
        self.assertIn(self.other_employee, employees)

    def test_report_applies_date_and_status_filters(self):
        approved = self.make_timesheet(status=Timesheet.Status.APPROVED)
        submitted = self.make_timesheet(
            employee=self.other_employee,
            status=Timesheet.Status.SUBMITTED,
        )
        self.make_entry(approved, day_offset=1, regular="4.00")
        self.make_entry(submitted, day_offset=2, regular="7.00")
        self.client.force_login(self.management_user)

        response = self.client.get(
            reverse("billability_report"),
            {
                "run": "1",
                "start": "2026-08-03",
                "end": "2026-08-03",
                "status": Timesheet.Status.APPROVED,
            },
        )

        employee_rows = {
            row["employee"]: row for row in response.context["rows"]
        }
        self.assertEqual(employee_rows[self.employee]["total_hours"], Decimal("4.00"))
        self.assertEqual(employee_rows[self.other_employee]["total_hours"], Decimal("0"))

    def test_report_ignores_entries_from_deleted_timesheets(self):
        deleted_sheet = self.make_timesheet(deleted=True)
        self.make_entry(deleted_sheet, regular="8.00")
        self.client.force_login(self.management_user)

        response = self.client.get(reverse("billability_report"), {"run": "1"})

        employee_row = next(
            row for row in response.context["rows"] if row["employee"] == self.employee
        )
        self.assertEqual(employee_row["total_hours"], Decimal("0"))
        self.assertEqual(employee_row["billability"], Decimal("0"))


class MyBillabilityReportTests(ReportViewTestBase):
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("my_billability_report"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('my_billability_report')}",
        )

    def test_report_only_uses_logged_in_users_entries(self):
        own_sheet = self.make_timesheet()
        other_sheet = self.make_timesheet(employee=self.other_employee)
        self.make_entry(own_sheet, regular="5.00")
        self.make_entry(other_sheet, regular="9.00")
        self.client.force_login(self.employee)

        response = self.client.get(reverse("my_billability_report"), {"run": "1"})

        self.assertEqual(response.context["summary"]["total_hours"], Decimal("5.00"))
        self.assertEqual(response.context["summary"]["entry_count"], 1)

    def test_report_splits_regular_overtime_doubletime_and_billability(self):
        timesheet = self.make_timesheet()
        self.make_entry(
            timesheet,
            row_order=1,
            job_number="26001",
            regular="4.00",
            overtime="2.00",
            doubletime="1.00",
        )
        self.make_entry(
            timesheet,
            row_order=2,
            job_number="",
            regular="3.00",
        )
        self.client.force_login(self.employee)

        response = self.client.get(reverse("my_billability_report"), {"run": "1"})

        summary = response.context["summary"]
        self.assertEqual(summary["total_regular"], Decimal("7.00"))
        self.assertEqual(summary["total_ot"], Decimal("2.00"))
        self.assertEqual(summary["total_dt"], Decimal("1.00"))
        self.assertEqual(summary["total_hours"], Decimal("10.00"))
        self.assertEqual(summary["billable_hours"], Decimal("7.00"))
        self.assertEqual(summary["non_billable_hours"], Decimal("3.00"))
        self.assertEqual(summary["billability"], Decimal("70.0"))

    def test_report_applies_date_and_status_filters(self):
        approved = self.make_timesheet(status=Timesheet.Status.APPROVED)
        submitted = self.make_timesheet(
            status=Timesheet.Status.SUBMITTED,
            week_start=self.week_start + timedelta(days=7),
        )
        self.make_entry(approved, day_offset=0, regular="4.00")
        self.make_entry(submitted, day_offset=0, regular="8.00")
        self.client.force_login(self.employee)

        response = self.client.get(
            reverse("my_billability_report"),
            {
                "run": "1",
                "start": "2026-08-09",
                "end": "2026-08-09",
                "status": Timesheet.Status.SUBMITTED,
            },
        )

        self.assertEqual(response.context["summary"]["total_hours"], Decimal("8.00"))
        self.assertEqual(response.context["summary"]["entry_count"], 1)

    def test_not_run_returns_zero_summary_and_no_detail_rows(self):
        self.client.force_login(self.employee)

        response = self.client.get(reverse("my_billability_report"))

        self.assertFalse(response.context["report_ran"])
        self.assertEqual(response.context["summary"]["total_hours"], Decimal("0"))
        self.assertEqual(response.context["detail_rows"], [])


class ProjectHoursReportTests(ReportViewTestBase):
    def test_regular_employee_cannot_open_project_report(self):
        self.client.force_login(self.employee)

        response = self.client.get(reverse("project_hours_report"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_project_manager_can_open_report(self):
        self.client.force_login(self.project_manager)

        response = self.client.get(reverse("project_hours_report"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["report_ran"])
        self.assertIsNone(response.context["summary"])

    def test_project_report_aggregates_totals_and_employee_rows(self):
        employee_sheet = self.make_timesheet(employee=self.employee)
        other_sheet = self.make_timesheet(employee=self.other_employee)
        self.make_entry(
            employee_sheet,
            job_number="26001",
            regular="5.00",
            overtime="1.00",
            doubletime="0.50",
        )
        self.make_entry(
            other_sheet,
            job_number="26001",
            regular="8.00",
        )
        self.client.force_login(self.project_manager)

        response = self.client.get(
            reverse("project_hours_report"),
            {"run": "1", "job_number": "26001"},
        )

        summary = response.context["summary"]
        self.assertEqual(summary["regular_hours"], Decimal("13.00"))
        self.assertEqual(summary["overtime_hours"], Decimal("1.00"))
        self.assertEqual(summary["doubletime_hours"], Decimal("0.50"))
        self.assertEqual(summary["total_hours"], Decimal("14.50"))
        self.assertEqual(summary["entry_count"], 2)
        self.assertEqual(response.context["employee_rows"][0]["employee"], self.other_employee)
        self.assertEqual(response.context["employee_rows"][0]["total_hours"], Decimal("8.00"))

    def test_project_report_matches_job_number_case_insensitively(self):
        timesheet = self.make_timesheet()
        self.make_entry(timesheet, job_number="AbC-123", regular="6.00")
        self.client.force_login(self.project_manager)

        response = self.client.get(
            reverse("project_hours_report"),
            {"run": "1", "job_number": "abc-123"},
        )

        self.assertEqual(response.context["summary"]["total_hours"], Decimal("6.00"))
        self.assertEqual(response.context["summary"]["entry_count"], 1)

    def test_project_report_filters_date_status_and_deleted_timesheets(self):
        approved = self.make_timesheet(status=Timesheet.Status.APPROVED)
        submitted = self.make_timesheet(
            employee=self.other_employee,
            status=Timesheet.Status.SUBMITTED,
        )
        deleted = self.make_timesheet(
            employee=self.project_manager,
            status=Timesheet.Status.APPROVED,
            deleted=True,
        )
        self.make_entry(approved, day_offset=1, job_number="26001", regular="4.00")
        self.make_entry(submitted, day_offset=2, job_number="26001", regular="6.00")
        self.make_entry(deleted, day_offset=1, job_number="26001", regular="9.00")
        self.client.force_login(self.project_manager)

        response = self.client.get(
            reverse("project_hours_report"),
            {
                "run": "1",
                "job_number": "26001",
                "start": "2026-08-03",
                "end": "2026-08-03",
                "status": Timesheet.Status.APPROVED,
            },
        )

        self.assertEqual(response.context["summary"]["total_hours"], Decimal("4.00"))
        self.assertEqual(response.context["summary"]["entry_count"], 1)

    def test_run_without_job_number_does_not_query_or_build_summary(self):
        self.client.force_login(self.project_manager)

        response = self.client.get(
            reverse("project_hours_report"),
            {"run": "1", "job_number": "   "},
        )

        self.assertTrue(response.context["report_ran"])
        self.assertEqual(response.context["job_number"], "")
        self.assertIsNone(response.context["summary"])
        self.assertEqual(response.context["detail_rows"], [])
