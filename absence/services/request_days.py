from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from absence.models import AbsenceRequest, AbsenceRequestDay


def weekdays_between(start_date: date, end_date: date):
    day = start_date
    while day <= end_date:
        if day.weekday() < 5:
            yield day
        day += timedelta(days=1)


def parse_daily_hours(data, start_date: date, end_date: date):
    result = []
    found_explicit = False
    for day in weekdays_between(start_date, end_date):
        key = f"day_hours_{day.isoformat()}"
        raw = data.get(key)
        if raw not in (None, ""):
            found_explicit = True
            try:
                hours = Decimal(str(raw))
            except (InvalidOperation, ValueError):
                raise ValueError(f"Enter a valid number of hours for {day:%m/%d/%Y}.")
            if hours < 0 or hours > 8:
                raise ValueError(f"Hours for {day:%m/%d/%Y} must be between 0 and 8.")
            if (hours * 4) != (hours * 4).to_integral_value():
                raise ValueError(f"Hours for {day:%m/%d/%Y} must be in 0.25-hour increments.")
            minutes = int(hours * 60)
        else:
            minutes = AbsenceRequest.WORKDAY_MINUTES
        result.append((day, minutes))
    if not result:
        raise ValueError("The selected date range does not contain any weekdays.")
    if not found_explicit:
        return result
    if not any(minutes > 0 for _, minutes in result):
        raise ValueError("At least one weekday must have requested hours greater than zero.")
    return result


def save_request_days(request: AbsenceRequest, daily_values):
    request.days.all().delete()
    rows = [
        AbsenceRequestDay(request=request, work_date=day, requested_minutes=minutes)
        for day, minutes in daily_values
        if minutes > 0
    ]
    AbsenceRequestDay.objects.bulk_create(rows)
    request.requested_minutes = sum(row.requested_minutes for row in rows)
    request.save(update_fields=["requested_minutes", "updated_at"])
    return request.requested_minutes


def request_day_minutes(request: AbsenceRequest):
    rows = list(request.days.all())
    if rows:
        return [(row.work_date, row.requested_minutes) for row in rows]
    weekdays = list(weekdays_between(request.start_date, request.end_date))
    remaining = request.requested_minutes
    values = []
    for day in weekdays:
        minutes = min(AbsenceRequest.WORKDAY_MINUTES, remaining) if remaining > 0 else 0
        if minutes:
            values.append((day, minutes))
            remaining -= minutes
    return values
