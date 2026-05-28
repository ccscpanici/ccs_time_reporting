from decimal import Decimal
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import render
from timesheets.models import TimeEntry, Timesheet
from timesheets.permissions import is_management_staff, is_project_manager


def _hours(entry):
    return (entry.regular_hours or Decimal("0")) + (entry.overtime_hours or Decimal("0")) + (entry.doubletime_hours or Decimal("0"))


@login_required
def reports_dashboard(request):
    return render(request, "reports/dashboard.html")


@user_passes_test(is_management_staff)
def billability_report(request):
    report_ran = request.GET.get("run") == "1"
    start = request.GET.get("start") or ""
    end = request.GET.get("end") or ""
    status = request.GET.get("status") or ""

    rows = []

    if report_ran:
        User = get_user_model()
        employees = (
            User.objects.filter(is_active=True)
            .exclude(Q(groups__name="Management Staff") | Q(is_superuser=True))
            .distinct()
            .order_by("last_name", "first_name", "username")
        )

        for employee in employees:
            entries = TimeEntry.objects.filter(timesheet__employee=employee, timesheet__deleted_at__isnull=True)
            if status:
                entries = entries.filter(timesheet__status=status)
            if start:
                entries = entries.filter(work_date__gte=start)
            if end:
                entries = entries.filter(work_date__lte=end)

            total_hours = Decimal("0")
            billable_hours = Decimal("0")
            for entry in entries.select_related("job"):
                h = _hours(entry)
                total_hours += h
                # Billability is based on whether a job number is associated, including free text.
                if entry.job_number or entry.job_id:
                    billable_hours += h

            non_billable_hours = total_hours - billable_hours
            billability = Decimal("0") if total_hours == 0 else (billable_hours / total_hours * Decimal("100"))
            rows.append({
                "employee": employee,
                "total_hours": total_hours,
                "billable_hours": billable_hours,
                "non_billable_hours": non_billable_hours,
                "billability": billability,
            })

    return render(request, "reports/billability.html", {
        "rows": rows,
        "start": start,
        "end": end,
        "status": status,
        "statuses": Timesheet.Status.choices,
        "report_ran": report_ran,
    })


@user_passes_test(is_project_manager)
def project_hours_report(request):
    report_ran = request.GET.get("run") == "1"
    job_number = (request.GET.get("job_number") or "").strip()
    start = request.GET.get("start") or ""
    end = request.GET.get("end") or ""
    status = request.GET.get("status") or ""

    summary = None
    employee_rows = []
    detail_rows = []

    if report_ran and job_number:
        entries = TimeEntry.objects.filter(
            timesheet__deleted_at__isnull=True,
            job_number__iexact=job_number,
        ).select_related("timesheet", "timesheet__employee", "job", "work_code").order_by(
            "work_date",
            "timesheet__employee__last_name",
            "timesheet__employee__first_name",
            "timesheet__employee__username",
            "row_order",
        )

        if start:
            entries = entries.filter(work_date__gte=start)
        if end:
            entries = entries.filter(work_date__lte=end)
        if status:
            entries = entries.filter(timesheet__status=status)

        total_regular = Decimal("0")
        total_ot = Decimal("0")
        total_dt = Decimal("0")
        by_employee = {}

        for entry in entries:
            regular = entry.regular_hours or Decimal("0")
            ot = entry.overtime_hours or Decimal("0")
            dt = entry.doubletime_hours or Decimal("0")
            total = regular + ot + dt

            total_regular += regular
            total_ot += ot
            total_dt += dt

            employee = entry.timesheet.employee
            employee_name = employee.get_full_name() or employee.get_username()

            if employee_name not in by_employee:
                by_employee[employee_name] = {
                    "employee": employee,
                    "employee_name": employee_name,
                    "regular_hours": Decimal("0"),
                    "overtime_hours": Decimal("0"),
                    "doubletime_hours": Decimal("0"),
                    "total_hours": Decimal("0"),
                }

            by_employee[employee_name]["regular_hours"] += regular
            by_employee[employee_name]["overtime_hours"] += ot
            by_employee[employee_name]["doubletime_hours"] += dt
            by_employee[employee_name]["total_hours"] += total

            detail_rows.append({
                "work_date": entry.work_date,
                "employee_name": employee_name,
                "regular_hours": regular,
                "overtime_hours": ot,
                "doubletime_hours": dt,
                "total_hours": total,
                "work_code": entry.work_code,
                "description": entry.description,
                "timesheet": entry.timesheet,
            })

        summary = {
            "job_number": job_number,
            "regular_hours": total_regular,
            "overtime_hours": total_ot,
            "doubletime_hours": total_dt,
            "total_hours": total_regular + total_ot + total_dt,
            "entry_count": len(detail_rows),
        }

        employee_rows = sorted(
            by_employee.values(),
            key=lambda row: (-row["total_hours"], row["employee_name"]),
        )

    return render(request, "reports/project_hours.html", {
        "job_number": job_number,
        "start": start,
        "end": end,
        "status": status,
        "statuses": Timesheet.Status.choices,
        "summary": summary,
        "employee_rows": employee_rows,
        "detail_rows": detail_rows,
        "report_ran": report_ran,
    })


@login_required
def my_billability_report(request):
    """Show the logged-in user's billability for a selected timeframe."""
    report_ran = request.GET.get("run") == "1"
    start = request.GET.get("start") or ""
    end = request.GET.get("end") or ""
    status = request.GET.get("status") or ""

    detail_rows = []
    summary = {
        "total_regular": Decimal("0"),
        "total_ot": Decimal("0"),
        "total_dt": Decimal("0"),
        "total_hours": Decimal("0"),
        "billable_hours": Decimal("0"),
        "non_billable_hours": Decimal("0"),
        "billability": Decimal("0"),
        "entry_count": 0,
    }

    if report_ran:
        entries = TimeEntry.objects.filter(
            timesheet__employee=request.user,
            timesheet__deleted_at__isnull=True,
        ).select_related("job", "work_code", "timesheet").order_by("work_date", "row_order")

        if status:
            entries = entries.filter(timesheet__status=status)
        if start:
            entries = entries.filter(work_date__gte=start)
        if end:
            entries = entries.filter(work_date__lte=end)

        total_regular = Decimal("0")
        total_ot = Decimal("0")
        total_dt = Decimal("0")
        total_hours = Decimal("0")
        billable_hours = Decimal("0")
        non_billable_hours = Decimal("0")

        for entry in entries:
            regular = entry.regular_hours or Decimal("0")
            ot = entry.overtime_hours or Decimal("0")
            dt = entry.doubletime_hours or Decimal("0")
            hours = regular + ot + dt

            total_regular += regular
            total_ot += ot
            total_dt += dt
            total_hours += hours

            is_billable = bool(entry.job_number or entry.job_id)

            if is_billable:
                billable_hours += hours
            else:
                non_billable_hours += hours

            detail_rows.append({
                "work_date": entry.work_date,
                "job_number": entry.job_display,
                "work_code": entry.work_code,
                "regular_hours": regular,
                "overtime_hours": ot,
                "doubletime_hours": dt,
                "total_hours": hours,
                "is_billable": is_billable,
                "description": entry.description,
                "timesheet": entry.timesheet,
            })

        billability = Decimal("0") if total_hours == 0 else (billable_hours / total_hours * Decimal("100"))

        summary = {
            "total_regular": total_regular,
            "total_ot": total_ot,
            "total_dt": total_dt,
            "total_hours": total_hours,
            "billable_hours": billable_hours,
            "non_billable_hours": non_billable_hours,
            "billability": billability,
            "entry_count": len(detail_rows),
        }

    return render(request, "reports/my_billability.html", {
        "start": start,
        "end": end,
        "status": status,
        "statuses": Timesheet.Status.choices,
        "summary": summary,
        "detail_rows": detail_rows,
        "report_ran": report_ran,
    })
