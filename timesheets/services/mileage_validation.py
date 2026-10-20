"""Validate reimbursement snapshots without mutating employee records."""
from decimal import Decimal, ROUND_HALF_UP

from ..models import Expense


def validate_timesheet_mileage(timesheet):
    """Reject mismatched or negative mileage reimbursements before workflow changes."""
    expenses = Expense.objects.filter(time_entry__timesheet=timesheet).select_related("time_entry")
    for expense in expenses:
        miles = expense.miles or Decimal("0")
        expected = (miles * timesheet.mileage_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        actual = expense.mileage.amount
        if miles < 0 or actual != expected:
            raise ValueError(
                f"Mileage discrepancy on {expense.time_entry.work_date}, "
                f"row {expense.time_entry.row_order}: {miles} miles, "
                f"stored ${actual}, expected ${expected}. Correct before proceeding."
            )
