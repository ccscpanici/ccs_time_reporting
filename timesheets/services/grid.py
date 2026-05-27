from decimal import Decimal
from .helpers import as_decimal


def build_timesheet_grid(timesheet):
    """Return seven date groups, padded to the configured rows per day."""
    grid = []
    for work_date in timesheet.week_dates:
        entries = list(timesheet.entries.filter(work_date=work_date).select_related("job", "work_code", "expense", "part_entry").order_by("row_order"))
        rows = []
        for row_order in range(1, timesheet.entries_per_day + 1):
            entry = next((item for item in entries if item.row_order == row_order), None)
            rows.append({"row_order": row_order, "entry": entry})
        grid.append({
            "work_date": work_date,
            "overnight_stay": any(entry.overnight_stay for entry in entries),
            "rows": rows,
            "entry_count": len(entries),
        })
    return grid


def is_blank_row(row):
    keys = ["job_number", "work_code", "regular_hours", "overtime_hours", "doubletime_hours", "description"]
    return not any(row.get(key) for key in keys)
