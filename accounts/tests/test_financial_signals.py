"""Tests for automatic employee financial profile creation."""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import EmployeeFinancialProfile, EmployeeProfile


class EmployeeFinancialProfileSignalTests(TestCase):
    def create_employee(self, username):
        with patch("accounts.signals.send_new_account_notification"):
            user = get_user_model().objects.create_user(
                username=username,
                password="test-password-not-for-production",
            )
        employee, _ = EmployeeProfile.objects.get_or_create(user=user)
        return employee

    def test_new_employee_receives_default_financial_profile(self):
        employee = self.create_employee("financial_signal_new")
        financial = EmployeeFinancialProfile.objects.get(employee=employee)

        self.assertEqual(financial.annual_salary, Decimal("0"))
        self.assertEqual(financial.annual_working_hours, 2080)
        self.assertEqual(financial.customer_billing_rate, Decimal("140"))
        self.assertTrue(financial.include_in_overhead)

    def test_updating_employee_does_not_overwrite_financial_profile(self):
        employee = self.create_employee("financial_signal_existing")
        financial = EmployeeFinancialProfile.objects.get(employee=employee)
        financial.annual_salary = Decimal("85000.00")
        financial.customer_billing_rate = Decimal("175.00")
        financial.include_in_overhead = False
        financial.save()

        employee.title = "Engineer"
        employee.save()

        financial.refresh_from_db()
        self.assertEqual(financial.annual_salary, Decimal("85000.00"))
        self.assertEqual(financial.customer_billing_rate, Decimal("175.00"))
        self.assertFalse(financial.include_in_overhead)
        self.assertEqual(EmployeeFinancialProfile.objects.filter(employee=employee).count(), 1)
