from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from pypdf import PdfReader

from absence.models import PTOAccount, PTOAccountChange, PTOImport, PTOImportRow
from absence.services.time_values import parse_hhmm


ROW_RE = re.compile(
    r"^(?P<name>.+?)\s+"
    r"(?P<sick_available>-?\d+:\d{2})\s+"
    r"(?P<sick_used>-?\d+:\d{2})\s+"
    r"(?P<vacation_available>-?\d+:\d{2})\s+"
    r"(?P<vacation_used>-?\d+:\d{2})\s*$"
)

DATE_LONG_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"(\d{1,2}),\s+(\d{4})\b",
    re.IGNORECASE,
)
DATE_SHORT_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")


@dataclass(frozen=True)
class ParsedPTORow:
    row_number: int
    employee_name: str
    sick_available_minutes: int
    sick_used_minutes: int
    vacation_available_minutes: int
    vacation_used_minutes: int


def extract_pdf_text(path_or_file) -> str:
    reader = PdfReader(path_or_file)
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def parse_report_date(text: str):
    long_match = DATE_LONG_RE.search(text)
    if long_match:
        return datetime.strptime(long_match.group(0), "%B %d, %Y").date()
    short_match = DATE_SHORT_RE.search(text)
    if short_match:
        month, day, year = map(int, short_match.groups())
        if year < 100:
            year += 2000
        return datetime(year, month, day).date()
    return None


def parse_pto_text(text: str) -> list[ParsedPTORow]:
    rows = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = " ".join(raw_line.split())
        if not line:
            continue
        match = ROW_RE.match(line)
        if not match:
            continue
        name = match.group("name").strip()
        # Prevent the report header from accidentally becoming an employee.
        if "employee" in name.lower() and "sick" in name.lower():
            continue
        rows.append(
            ParsedPTORow(
                row_number=line_number,
                employee_name=name,
                sick_available_minutes=parse_hhmm(match.group("sick_available")),
                sick_used_minutes=parse_hhmm(match.group("sick_used")),
                vacation_available_minutes=parse_hhmm(match.group("vacation_available")),
                vacation_used_minutes=parse_hhmm(match.group("vacation_used")),
            )
        )
    return rows


def _name_parts(report_name: str):
    report_name = " ".join(report_name.replace(".", " ").split())
    if "," not in report_name:
        return None, None
    last, remainder = [part.strip() for part in report_name.split(",", 1)]
    first = remainder.split()[0] if remainder else ""
    return first, last


def match_employee(report_name: str):
    User = get_user_model()
    first, last = _name_parts(report_name)
    if not first or not last:
        return None, PTOImportRow.MatchStatus.INVALID, "Expected employee name in 'Last, First' format."

    matches = list(User.objects.filter(first_name__iexact=first, last_name__iexact=last, is_active=True, employee_profile__isnull=False)[:3])
    if len(matches) == 1:
        return matches[0], PTOImportRow.MatchStatus.MATCHED, ""
    if len(matches) > 1:
        return None, PTOImportRow.MatchStatus.AMBIGUOUS, "Multiple active users have this first and last name."
    return None, PTOImportRow.MatchStatus.UNMATCHED, "No active employee profile matched this name."


def build_import_preview(pto_import: PTOImport) -> PTOImport:
    try:
        text = extract_pdf_text(pto_import.source_file.path)
        parsed_rows = parse_pto_text(text)
        if not parsed_rows:
            raise ValueError("No PTO employee rows were found in the uploaded PDF.")

        pto_import.rows.all().delete()
        pto_import.report_date = parse_report_date(text)
        pto_import.error_message = ""
        pto_import.status = PTOImport.Status.PREVIEW
        pto_import.save(update_fields=["report_date", "error_message", "status"])

        rows_to_create = []
        for parsed in parsed_rows:
            employee, match_status, message = match_employee(parsed.employee_name)
            rows_to_create.append(
                PTOImportRow(
                    pto_import=pto_import,
                    row_number=parsed.row_number,
                    employee_name=parsed.employee_name,
                    employee=employee,
                    match_status=match_status,
                    match_message=message,
                    sick_available_minutes=parsed.sick_available_minutes,
                    sick_used_minutes=parsed.sick_used_minutes,
                    vacation_available_minutes=parsed.vacation_available_minutes,
                    vacation_used_minutes=parsed.vacation_used_minutes,
                )
            )
        PTOImportRow.objects.bulk_create(rows_to_create)
        return pto_import
    except Exception as exc:
        pto_import.status = PTOImport.Status.FAILED
        pto_import.error_message = str(exc)
        pto_import.save(update_fields=["status", "error_message"])
        raise


def _snapshot(account: PTOAccount):
    return {
        "vacation_weeks_per_year": account.vacation_weeks_per_year,
        "vacation_balance_minutes": account.vacation_balance_minutes,
        "sick_balance_minutes": account.sick_balance_minutes,
        "vacation_used_minutes": account.vacation_used_minutes,
        "sick_used_minutes": account.sick_used_minutes,
        "balance_as_of": account.balance_as_of,
    }


def _record_change(account, old, new, *, user, pto_import=None, source, note=""):
    return PTOAccountChange.objects.create(
        pto_account=account,
        pto_import=pto_import,
        source=source,
        old_vacation_weeks_per_year=old["vacation_weeks_per_year"],
        new_vacation_weeks_per_year=new["vacation_weeks_per_year"],
        old_vacation_balance_minutes=old["vacation_balance_minutes"],
        new_vacation_balance_minutes=new["vacation_balance_minutes"],
        old_sick_balance_minutes=old["sick_balance_minutes"],
        new_sick_balance_minutes=new["sick_balance_minutes"],
        old_vacation_used_minutes=old["vacation_used_minutes"],
        new_vacation_used_minutes=new["vacation_used_minutes"],
        old_sick_used_minutes=old["sick_used_minutes"],
        new_sick_used_minutes=new["sick_used_minutes"],
        old_balance_as_of=old["balance_as_of"],
        new_balance_as_of=new["balance_as_of"],
        changed_by=user,
        note=note,
    )


@transaction.atomic
def apply_pto_import(pto_import: PTOImport, user):
    if pto_import.status != PTOImport.Status.PREVIEW:
        raise ValueError("Only an import in preview status can be applied.")

    matched_rows = list(
        pto_import.rows
        .filter(
            match_status=PTOImportRow.MatchStatus.MATCHED,
            employee__isnull=False,
        )
        .select_related("employee")
    )

    if not matched_rows:
        raise ValueError("This import does not contain any matched employees to apply.")

    employee_ids = [row.employee_id for row in matched_rows]
    if len(employee_ids) != len(set(employee_ids)):
        raise ValueError(
            "Two or more matched report rows point to the same employee. "
            "Correct the duplicate matches before applying the import."
        )

    for row in matched_rows:
        account, _ = PTOAccount.objects.get_or_create(employee=row.employee)

        old = _snapshot(account)

        account.vacation_balance_minutes = row.vacation_available_minutes
        account.sick_balance_minutes = row.sick_available_minutes
        account.vacation_used_minutes = row.vacation_used_minutes
        account.sick_used_minutes = row.sick_used_minutes
        account.balance_as_of = pto_import.report_date or timezone.localdate()
        account.updated_by = user

        new = _snapshot(account)

        if old != new:
            account.save()
            _record_change(
                account,
                old,
                new,
                user=user,
                pto_import=pto_import,
                source=PTOAccountChange.Source.IMPORT,
                note=f"Imported from {pto_import.source_name}.",
            )

    pto_import.status = PTOImport.Status.APPLIED
    pto_import.applied_by = user
    pto_import.applied_at = timezone.now()
    pto_import.save(update_fields=["status", "applied_by", "applied_at"])

    return pto_import


def account_snapshot(account: PTOAccount):
    return _snapshot(account)


def record_manual_account_change(account: PTOAccount, old, user, *, note=""):
    new = _snapshot(account)
    if old == new:
        return None
    return _record_change(
        account,
        old,
        new,
        user=user,
        source=PTOAccountChange.Source.MANUAL,
        note=note,
    )
