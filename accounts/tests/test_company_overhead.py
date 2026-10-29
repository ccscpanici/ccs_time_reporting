"""Company overhead calculations, date validity, and financial admin security."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import CompanyOverhead


class CompanyOverheadTests(TestCase):
    def make_expense(self, name="Rent", **kwargs):
        data = dict(name=name, amount=Decimal("100.00"), frequency="monthly", effective_start=date(2026, 1, 1))
        data.update(kwargs)
        return CompanyOverhead.objects.create(**data)

    def test_annualization_and_date_filtering(self):
        self.make_expense()
        self.make_expense("Insurance", amount=Decimal("500.00"), frequency="annual")
        self.make_expense("Old", amount=Decimal("50.00"), effective_end=date(2026, 6, 30))
        self.make_expense("Future", amount=Decimal("200.00"), effective_start=date(2027, 1, 1))
        self.make_expense("Disabled", amount=Decimal("900.00"), active=False)
        self.assertEqual(CompanyOverhead.annual_total_on(date(2026, 6, 30)), Decimal("2300.00"))
        self.assertEqual(CompanyOverhead.annual_total_on(date(2026, 7, 1)), Decimal("1700.00"))
        self.assertEqual(CompanyOverhead.annual_total_on(date(2025, 12, 31)), Decimal("0.00"))

    def test_invalid_amount_and_dates(self):
        bad = self.make_expense(amount=Decimal("10.00"))
        bad.amount = Decimal("-1.00")
        with self.assertRaises(ValidationError):
            bad.full_clean()
        bad.amount = Decimal("10.00")
        bad.effective_end = date(2025, 12, 31)
        with self.assertRaises(ValidationError):
            bad.full_clean()

    def test_overhead_admin_access_is_superuser_only(self):
        User = get_user_model()
        regular = User.objects.create_user(username="regular", password="pass")
        staff = User.objects.create_user(username="staff", password="pass", is_staff=True)
        superuser = User.objects.create_superuser(username="boss", email="boss@example.com", password="pass")
        expense = self.make_expense()
        urls = [
            reverse("admin:accounts_companyoverhead_changelist"),
            reverse("admin:accounts_companyoverhead_add"),
            reverse("admin:accounts_companyoverhead_change", args=[expense.pk]),
            reverse("admin:accounts_companyoverhead_delete", args=[expense.pk]),
        ]
        for user in (regular, staff):
            self.client.force_login(user)
            for url in urls:
                response = self.client.get(url)
                self.assertNotEqual(response.status_code, 200)
        self.client.force_login(superuser)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200)
