from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from absence.models import AbsenceRequest, PTOAccount
from absence.services.request_days import request_day_minutes


PAY_PERIOD_ANCHOR_END = date(2026, 9, 11)
PAY_PERIOD_DAYS = 14
MINUTES_PER_WEEK = 40 * 60
MINUTES_PER_WORKDAY = 8 * 60


@dataclass(frozen=True)
class VacationSummary:
    annual_entitlement_minutes: int
    vacation_accrual_minutes: int
    vacation_used_minutes: int
    vacation_balance_minutes: int
    approved_vacation_pending_minutes: int
    projected_vacation_balance_minutes: int


def annual_vacation_minutes(vacation_weeks_per_year) -> int:
    weeks = Decimal(vacation_weeks_per_year or 0)
    minutes = weeks * MINUTES_PER_WEEK
    return int(minutes.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def pay_period_end_for(day: date) -> date:
    delta_days = (day - PAY_PERIOD_ANCHOR_END).days
    period_index = delta_days // PAY_PERIOD_DAYS
    period_end = PAY_PERIOD_ANCHOR_END + timedelta(days=period_index * PAY_PERIOD_DAYS)
    if day > period_end:
        period_end += timedelta(days=PAY_PERIOD_DAYS)
    return period_end


def pending_expiration_for(day: date) -> date:
    """Return the end of the pay period after the period containing ``day``."""

    return pay_period_end_for(day) + timedelta(days=PAY_PERIOD_DAYS)


def iter_workdays(start_date: date, end_date: date):
    day = start_date
    while day <= end_date:
        if day.weekday() < 5:
            yield day
        day += timedelta(days=1)


def approved_vacation_pending_minutes(employee, *, as_of: date | None = None) -> int:
    """Calculate approved vacation that should still be treated as pending.

    Each approved weekday remains pending through the end of the pay period
    immediately following the pay period containing that vacation day.
    """

    as_of = as_of or timezone.localdate()
    requests = (
        AbsenceRequest.objects.filter(
            employee=employee,
            absence_type=AbsenceRequest.AbsenceType.VACATION,
            status=AbsenceRequest.Status.APPROVED,
        )
        .prefetch_related("days")
    )

    pending_minutes = 0
    for request in requests:
        for day, minutes in request_day_minutes(request):
            if as_of <= pending_expiration_for(day):
                pending_minutes += minutes
    return pending_minutes


def vacation_summary(account: PTOAccount, *, as_of: date | None = None) -> VacationSummary:
    annual_minutes = annual_vacation_minutes(account.vacation_weeks_per_year)
    vacation_used = account.vacation_used_minutes
    vacation_balance = annual_minutes - vacation_used
    pending = approved_vacation_pending_minutes(account.employee, as_of=as_of)

    return VacationSummary(
        annual_entitlement_minutes=annual_minutes,
        vacation_accrual_minutes=account.vacation_balance_minutes,
        vacation_used_minutes=vacation_used,
        vacation_balance_minutes=vacation_balance,
        approved_vacation_pending_minutes=pending,
        projected_vacation_balance_minutes=vacation_balance - pending,
    )
