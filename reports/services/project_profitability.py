"""Read-only project financial estimates based on current employee assumptions."""
from collections import defaultdict
from decimal import Decimal
from accounts.models import EmployeeFinancialProfile
from timesheets.models import TimeEntry, Timesheet

ZERO = Decimal("0.00")
ELIGIBLE_STATUSES = (
    Timesheet.Status.APPROVED,
    Timesheet.Status.EXPORTED_TO_QUICKBOOKS,
    Timesheet.Status.INVOICED,
)


def project_profitability(*, start=None, end=None, job_number=None):
    """Return estimates for finalized timesheets; rates are current, not historical snapshots.

    Job-number association is the existing application's billability proxy. No
    invoice revenue, expense reimbursements, parts, or OT multipliers are applied.
    """
    entries = TimeEntry.objects.filter(
        timesheet__deleted_at__isnull=True,
        timesheet__status__in=ELIGIBLE_STATUSES,
    ).select_related("job", "timesheet__employee")
    if start:
        entries = entries.filter(work_date__gte=start)
    if end:
        entries = entries.filter(work_date__lte=end)
    financials = {
        profile.employee.user_id: profile
        for profile in EmployeeFinancialProfile.objects.select_related("employee__user")
    }
    rows = {}
    excluded_missing_rates = 0
    for entry in entries.iterator():
        number = (entry.job_display or "").strip()
        if not number:
            continue
        if job_number and number.casefold() != job_number.strip().casefold():
            continue
        profile = financials.get(entry.timesheet.employee_id)
        if profile is None:
            excluded_missing_rates += 1
            continue
        key = number.casefold()
        if key not in rows:
            rows[key] = {
                "job_number": number,
                "description": entry.job.description if entry.job_id else "",
                "total_hours": ZERO,
                "billable_hours": ZERO,
                "nonbillable_hours": ZERO,
                "labor_cost": ZERO,
                "estimated_revenue": ZERO,
                "estimated_profit": ZERO,
                "profit_margin": ZERO,
            }
        row = rows[key]
        if not row["description"] and entry.job_id:
            row["description"] = entry.job.description
        hours = entry.total_hours
        row["total_hours"] += hours
        row["billable_hours"] += hours
        row["labor_cost"] += hours * profile.burn_rate_on(entry.work_date)
        row["estimated_revenue"] += hours * profile.customer_billing_rate
    result = []
    for row in rows.values():
        for field in ("labor_cost", "estimated_revenue"):
            row[field] = row[field].quantize(Decimal("0.01"))
        row["estimated_profit"] = row["estimated_revenue"] - row["labor_cost"]
        if row["estimated_revenue"]:
            row["profit_margin"] = (row["estimated_profit"] / row["estimated_revenue"] * 100).quantize(Decimal("0.1"))
        result.append(row)
    result.sort(key=lambda row: row["job_number"].casefold())
    return {"rows": result, "excluded_missing_rates": excluded_missing_rates}
