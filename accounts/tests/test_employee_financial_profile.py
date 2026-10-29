"""Regression tests for restricted employee financial profiles."""
from datetime import date
from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from accounts.admin import EmployeeFinancialProfileAdmin
from accounts.forms import EmployeeProfileForm
from accounts.models import CompanyOverhead, EmployeeProfile, EmployeeFinancialProfile

User = get_user_model()


class EmployeeFinancialProfileTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="engineer1")
        self.user2 = User.objects.create_user(username="engineer2")
        self.user3 = User.objects.create_user(username="internal")
        self.profiles = []
        for user in (self.user1, self.user2, self.user3):
            employee, _ = EmployeeProfile.objects.get_or_create(user=user)
            financial, _ = EmployeeFinancialProfile.objects.get_or_create(employee=employee)
            self.profiles.append(financial)
        CompanyOverhead.objects.create(
            name="Rent",
            amount=Decimal("1000"),
            frequency="monthly",
            effective_start=date(2026, 1, 1),
        )

    def test_equal_overhead_and_exclusion(self):
        first, second, internal = self.profiles
        self.assertEqual(first.allocated_annual_overhead_on(date(2026, 10, 1)), Decimal("4000.00"))
        internal.include_in_overhead = False
        internal.save()
        self.assertEqual(first.allocated_annual_overhead_on(date(2026, 10, 1)), Decimal("6000.00"))
        self.assertEqual(second.allocated_annual_overhead_on(date(2026, 10, 1)), Decimal("6000.00"))
        self.assertEqual(internal.allocated_annual_overhead_on(date(2026, 10, 1)), Decimal("0.00"))

    def test_inactive_employee_excluded(self):
        self.user3.is_active = False
        self.user3.save()
        self.assertEqual(self.profiles[0].allocated_annual_overhead_on(date(2026, 10, 1)), Decimal("6000.00"))

    def test_burn_rate_and_direct_cost(self):
        profile = self.profiles[0]
        profile.annual_salary = Decimal("104000")
        profile.annual_benefits = Decimal("10400")
        self.assertEqual(profile.direct_annual_cost, Decimal("114400"))
        self.assertEqual(profile.total_annual_cost_on(date(2026, 10, 1)), Decimal("118400.00"))
        self.assertEqual(profile.burn_rate_on(date(2026, 10, 1)), Decimal("56.92"))

    def test_validation(self):
        profile = self.profiles[0]
        profile.annual_salary = Decimal("-1")
        profile.annual_working_hours = Decimal("0")
        with self.assertRaises(ValidationError):
            profile.full_clean()

    def test_regular_profile_form_excludes_finances(self):
        form = EmployeeProfileForm(instance=self.profiles[0].employee)
        self.assertNotIn("annual_salary", form.fields)
        self.assertNotIn("include_in_overhead", form.fields)

    def test_admin_permissions(self):
        model_admin = EmployeeFinancialProfileAdmin(EmployeeFinancialProfile, admin.site)
        factory = RequestFactory()
        ordinary = User.objects.create_user(username="staff", is_staff=True)
        privileged = User.objects.create_superuser(
            username="super", email="super@example.com", password="test"
        )
        for user, allowed in ((ordinary, False), (privileged, True)):
            request = factory.get("/admin/accounts/employeefinancialprofile/")
            request.user = user
            for method in (
                "has_module_permission", "has_view_permission", "has_add_permission",
                "has_change_permission", "has_delete_permission",
            ):
                self.assertEqual(getattr(model_admin, method)(request), allowed)
