"""Mileage validation and post-approval immutability regression tests."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from timesheets.models import Expense, Timesheet
from timesheets.services.mileage_validation import validate_timesheet_mileage
from timesheets.tests.factories import make_user, make_timesheet, make_time_entry


class MileageHotfixTests(TestCase):
    def setUp(self):
        self.user = make_user(username="mileage_hotfix_user")
        self.timesheet = make_timesheet(
            employee=self.user, week_start=date(2026, 10, 11),
            mileage_rate=Decimal("0.760"),
        )
        self.entry = make_time_entry(timesheet=self.timesheet, work_date=date(2026, 10, 15))

    def test_mileage_calculates_and_validates(self):
        for miles, expected in [(60, "45.60"), (90, "68.40"), (110, "83.60"), (165, "125.40")]:
            expense, _ = Expense.objects.update_or_create(
                time_entry=self.entry, defaults={"miles": Decimal(miles)}
            )
            self.assertEqual(expense.mileage.amount, Decimal(expected))
            validate_timesheet_mileage(self.timesheet)

    def test_mismatch_is_rejected_without_repairing_data(self):
        expense = Expense.objects.create(time_entry=self.entry, miles=Decimal("60"))
        Expense.objects.filter(pk=expense.pk).update(mileage=Decimal("4.56"))
        with self.assertRaisesRegex(ValueError, "Mileage discrepancy"):
            validate_timesheet_mileage(self.timesheet)
        expense.refresh_from_db()
        self.assertEqual(expense.mileage.amount, Decimal("4.56"))

    def test_approved_expense_cannot_be_saved(self):
        expense = Expense.objects.create(time_entry=self.entry, miles=Decimal("165"))
        self.timesheet.status = Timesheet.Status.APPROVED
        self.timesheet.save(update_fields=["status"])
        expense.miles = Decimal("16")
        with self.assertRaisesRegex(ValueError, "locked"):
            expense.save()
        expense.refresh_from_db()
        self.assertEqual(expense.miles, Decimal("165"))
        self.assertEqual(expense.mileage.amount, Decimal("125.40"))
