from __future__ import annotations

import re
from datetime import date, timedelta

_TIME_RE = re.compile(r"^\s*(?P<sign>-)?(?P<hours>\d+):(?P<minutes>\d{1,2})\s*$")


def parse_hhmm(value: str) -> int:
    """Convert signed HHH:MM text to signed integer minutes."""
    match = _TIME_RE.match(str(value or ""))
    if not match:
        raise ValueError(f"Invalid time value: {value!r}")
    minutes = int(match.group("minutes"))
    if minutes >= 60:
        raise ValueError(f"Minutes must be less than 60: {value!r}")
    total = int(match.group("hours")) * 60 + minutes
    return -total if match.group("sign") else total


def format_hhmm(value: int | None) -> str:
    if value is None:
        return "—"
    sign = "-" if value < 0 else ""
    value = abs(int(value))
    hours, minutes = divmod(value, 60)
    return f"{sign}{hours}:{minutes:02d}"


def count_workdays(start: date, end: date) -> int:
    if end < start:
        return 0
    current = start
    count = 0
    while current <= end:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


def is_full_employment_week_range(start: date | None, end: date | None) -> bool:
    if not start or not end or end < start:
        return False
    if start.weekday() != 0 or end.weekday() != 4:  # Monday through Friday
        return False
    return (end - start).days % 7 == 4
