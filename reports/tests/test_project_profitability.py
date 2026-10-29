"""Regression coverage for restricted project financial estimates."""
from decimal import Decimal
from django.urls import reverse
from accounts.models import EmployeeProfile, EmployeeFinancialProfile
from reports.services.project_profitability import project_profitability
from reports.tests.test_views import ReportViewTestBase
from timesheets.models import Timesheet


class ProjectProfitabilityTests(ReportViewTestBase):
    def test_superuser_only(self):
        url = reverse("project_profitability_report")
        for user in (self.employee, self.project_manager, self.management_user):
            self.client.force_login(user)
            response = self.client.get(url, {"run": "1"})
            self.assertNotEqual(response.status_code, 200)
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_estimates_include_free_text_and_exclude_drafts(self):
        employee_profile, _ = EmployeeProfile.objects.get_or_create(user=self.employee)
        profile, _ = EmployeeFinancialProfile.objects.get_or_create(employee=employee_profile)
        profile.annual_salary = Decimal("104000")
        profile.customer_billing_rate = Decimal("140")
        profile.save()
        approved = self.make_timesheet(status=Timesheet.Status.APPROVED)
        self.make_entry(approved, job_number="26001", regular="8")
        draft = self.make_timesheet(status=Timesheet.Status.DRAFT, week_start=self.week_start.replace(day=9))
        self.make_entry(draft, job_number="26001", regular="4")
        result = project_profitability(job_number="26001")
        self.assertEqual(len(result["rows"]), 1)
        row = result["rows"][0]
        self.assertEqual(row["total_hours"], Decimal("8"))
        self.assertEqual(row["estimated_revenue"], Decimal("1120"))
        self.assertEqual(row["labor_cost"], Decimal("400"))

    def test_invalid_date_is_rejected(self):
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(reverse("project_profitability_report"), {"run":"1", "start":"not-a-date"}).status_code, 400)
