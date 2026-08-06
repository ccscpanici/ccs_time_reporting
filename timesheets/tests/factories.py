"""Small dependency-free factories used by the Django test suite.

These helpers intentionally avoid factory-boy/model-bakery so the core suite can
run with only the production requirements installed.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from accounts.models import EmployeeProfile
from timesheets.models import Customer, Job, TimeEntry, Timesheet

User = get_user_model()


def make_user(*, username: str, password: str = "test-password", **overrides: Any):
    values = {
        "first_name": username.replace("_", " ").title(),
        "last_name": "User",
        "email": f"{username}@gotoccs.com",
    }
    values.update(overrides)
    return User.objects.create_user(username=username, password=password, **values)


def get_group(name: str) -> Group:
    group, _ = Group.objects.get_or_create(name=name)
    return group


def add_user_to_group(user, name: str) -> Group:
    group = get_group(name)
    user.groups.add(group)
    return group


def make_employee_profile(*, user, supervisor=None, **overrides: Any) -> EmployeeProfile:
    values = {"supervisor": supervisor}
    values.update(overrides)
    return EmployeeProfile.objects.create(user=user, **values)


def make_customer(*, name: str = "Test Customer", **overrides: Any) -> Customer:
    return Customer.objects.create(name=name, **overrides)


def make_job(*, job_number: str = "26001", **overrides: Any) -> Job:
    values = {
        "description": f"Description for {job_number}",
        "year": 2026,
        "job_month": 1,
        "job_status": Job.STATUS_ACTIVE,
        "invoice_status": Job.INVOICE_STATUS_PROGRESS,
        "active": True,
    }
    values.update(overrides)
    return Job.objects.create(job_number=job_number, **values)


def make_timesheet(
    *,
    employee,
    week_start: date,
    status: str = Timesheet.Status.DRAFT,
    **overrides: Any,
) -> Timesheet:
    values = {
        "mileage_rate": Decimal("0.72"),
        "entries_per_day": 5,
        "template_entries_per_day": 5,
    }
    values.update(overrides)
    return Timesheet.objects.create(
        employee=employee,
        week_start=week_start,
        status=status,
        **values,
    )


def make_time_entry(
    *,
    timesheet: Timesheet,
    work_date: date | None = None,
    row_order: int = 1,
    **overrides: Any,
) -> TimeEntry:
    values = {
        "job_number": "26001",
        "regular_hours": Decimal("0.00"),
        "overtime_hours": Decimal("0.00"),
        "doubletime_hours": Decimal("0.00"),
        "description": "Test work",
    }
    values.update(overrides)
    return TimeEntry.objects.create(
        timesheet=timesheet,
        work_date=work_date or timesheet.week_start,
        row_order=row_order,
        **values,
    )
