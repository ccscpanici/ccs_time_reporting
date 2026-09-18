# CCS Online Time Reporting

Internal Django application for CCS time reporting, expense tracking, job reporting, PTO management, and employee absence requests.

## Stack

- Django 5.2 LTS-compatible stack
- PostgreSQL in CCS environments
- Bootstrap 5.3.8
- django-money / py-moneyed
- openpyxl for Excel import/export
- ReportLab for PDF generation
- pypdf for PTO report ingestion

## Timesheets

- Users can create, edit, upload, replace, delete/void, and submit weekly timesheets.
- Work weeks are Sunday-based.
- A user can upload the same week again; the importer replaces the existing week unless it is approved.
- The web editor groups time entries by date and supports configurable rows per date.
- Job numbers are entered as free text and linked to a matching `Job` where possible.
- Excel export is available when each date has 5 or fewer time entries; larger timesheets use the flat PDF format.
- Submitted timesheets retain historical submission artifacts.
- Mileage and overnight rates are maintained by year in the database.
- Money fields use `django-money` rather than floating-point values.

## Management reporting

Management reports are available under `/reports/` to authorized users. Reports include employee billability, project-hour reporting, and related management views.

## Employee profiles

Employee profiles contain office information, home-address information, and the employee-to-supervisor relationship used for timesheet and absence approval routing.

# Absence Management

The `absence` Django application manages PTO balances, absence requests, supervisor approvals, PTO report imports, audit history, and finalized absence-request PDFs.

## Absence types

The initial application supports:

- Vacation
- Sick
- Personal Time

Vacation and personal-time requests submitted less than two weeks before the first requested date are allowed to proceed but are flagged for the approver. Sick requests are exempt from the two-week rule.

## PTO accounts

Each employee may have one `PTOAccount` containing:

- Vacation entitlement in weeks per year
- Vacation accrual (the payroll report field labeled `Vacation Available`)
- Vacation used from payroll
- Sick available from payroll
- Sick used from payroll
- Balance effective/as-of date
- Last updater and update timestamp

PTO hour values are stored as signed integer minutes. This preserves values such as `73:01`, `-26:16`, and `126:45` exactly without decimal-hour rounding.

Vacation entitlement in weeks per year is maintained manually by authorized supervisors. Imported Paid Time Off List reports update Vacation Accrual, Vacation Used, Sick Available, and Sick Used but do not overwrite the employee's manually maintained vacation entitlement.

The CCS vacation values are calculated as:

- `Vacation Balance = annual vacation entitlement - Vacation Used`
- `Projected Vacation Balance = Vacation Balance - Approved Vacation Pending`

The payroll report's `Vacation Available` value is retained and displayed as **Vacation Accrual** for reference; it is not used as the CCS remaining-vacation balance. Sick Available is imported exactly as reported. Negative Sick Available values are expected, because CCS does not maintain a fixed sick-time entitlement bank.

## PTO balance management

Project managers/supervisors may edit PTO information for their direct reports. Management Staff may edit PTO information for all active employees.

Every manual PTO change creates a `PTOAccountChange` audit record containing the previous and new values, balance-as-of dates, user making the change, timestamp, source, and optional notes.

## PTO report import

Management Staff can upload the CCS **Paid Time Off List** PDF under the Absence application.

The importer reads:

- Employee
- Sick Available
- Sick Used
- Vacation Available
- Vacation Used

The workflow is:

1. Upload the PTO PDF.
2. Parse the report date and employee rows.
3. Match `Last, First` report names to active CCS users.
4. Preview current and imported balances.
5. Optionally resolve unmatched or ambiguous employee rows.
6. Confirm the import.
7. Update only matched employee PTO accounts and create audit records.

The uploaded report is preserved in the application's media storage and represented by `PTOImport` / `PTOImportRow` records. Unmatched or ambiguous rows do not block an import; they are preserved for audit and skipped. At least one matched employee is required to apply an import.

The imported report is treated as the authoritative source for Vacation Used and the payroll sick values. Online timesheet vacation entries are not used for PTO accounting because not every CCS employee submits timesheets through this application.

## Absence requests

Employees create requests under `/absence/`.

An `AbsenceRequest` records:

- Employee
- Supervisor/manager snapshot
- Absence type
- First and last requested dates
- Requested work time
- Outlook calendar acknowledgment for vacation
- Two-week notice flag
- Vacation entitlement / Vacation Used / calculated Vacation Balance snapshot at submission
- Approved Vacation Pending snapshot
- Projected vacation balance after the request
- Approval state and approval audit fields
- Negative-vacation exception data when applicable

The initial requested-time calculation treats each Monday-Friday date in the requested range as an 8-hour workday. Weekend dates are not counted toward requested PTO time.

Authenticated user identities and timestamps replace handwritten signatures.

## Approval workflow

Normal workflow:

1. Employee creates a draft.
2. Employee submits the request.
3. Current PTO values and supervisor assignment are snapshotted.
4. The assigned supervisor reviews the request.
5. The supervisor approves or denies it.
6. Finalized requests generate an archived PDF.

Management Staff can review all pending requests. Project managers see requests assigned to them.

## Negative vacation balance exceptions

The current CCS lower limit is `-40:00` vacation hours.

Approved Vacation Pending is calculated from finalized approved vacation requests. CCS pay periods are biweekly and anchored to the pay period ending Friday, September 11, 2026. Each approved vacation weekday remains pending through the end of the pay period immediately following the pay period containing that vacation day. Multi-day requests are evaluated one weekday at a time. Each request stores the actual requested minutes for each weekday, allowing partial days (for example, 4.00 hours) and quarter-hour increments from 0 through 8 hours per weekday.

If a new vacation request takes `Vacation Balance - Approved Vacation Pending - Requested Vacation` below `-40:00`, the employee must acknowledge the exception and supply unpaid dates covering complete Monday-through-Friday employment-week increments.

After normal supervisor approval, the request moves to **Pending Negative Balance Exception Approval**. Management Staff must then approve or deny the exception before the request is final.

## Absence PDF archive

Final approved or denied absence requests generate a PDF containing the request, per-workday requested hours, PTO snapshot, employee submission identity/timestamp, manager decision, and negative-balance exception information when applicable.

PDF filenames use:

```text
<EMPLOYEE_INITIALS>_<FIRST_ABSENCE_DATE>.pdf
```

Example:

```text
CP_20260830.pdf
```

The date is the first date of the absence request in `YYYYMMDD` format. Existing files are never overwritten. Filename collisions use suffixes:

```text
CP_20260830.pdf
CP_20260830_2.pdf
CP_20260830_3.pdf
```

The PDF archive root is configured with:

```text
ABSENCE_PDF_ROOT=/mounted/file/server/path
```

Do not hard-code the production file-server path in application code. In development, the archive defaults to `media/absence_requests/`.

Each archived document creates an `AbsenceArtifact` containing the filename, absolute archive path, generating user, timestamp, and SHA-256 checksum.

## Absence routes

- `/absence/` - my absence requests and PTO summary
- `/absence/new/` - create a request
- `/absence/<id>/` - request detail and approval history
- `/absence/<id>/edit/` - edit an unsubmitted draft
- `/absence/approvals/` - supervisor/management approval queue
- `/absence/pto/` - PTO balances for manageable employees
- `/absence/pto/<user_id>/edit/` - manual PTO update
- `/absence/pto/imports/` - PTO import history
- `/absence/pto/import/` - upload a Paid Time Off List PDF

## Absence data model

- `PTOAccount` - current employee PTO snapshot and vacation entitlement
- `PTOAccountChange` - manual/imported PTO audit history
- `PTOImport` - one uploaded PTO report
- `PTOImportRow` - one parsed employee row and employee match
- `AbsenceRequest` - employee request and approval workflow
- `AbsenceArtifact` - finalized archived PDF

# Configuration and setup

Install dependencies and initialize the application:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_all
python manage.py createsuperuser
python manage.py runserver
```

Local development:

```text
http://127.0.0.1:8000/
```

After pulling the Absence application changes, run:

```bash
python manage.py migrate
python manage.py check
python manage.py test absence --settings=ccs_time_reporting.test_settings -v 2
```

Then run the complete test suite before deployment:

```bash
python manage.py test --settings=ccs_time_reporting.test_settings
```

# Development approach

Significant changes should be developed and tested outside the production installation.

1. Make a code/database backup when appropriate.
2. Add or update automated tests.
3. Run targeted application tests.
4. Run `python manage.py check`.
5. Run the complete Django test suite.
6. Review migrations before applying them to production.
7. Commit the tested changes.
8. Deploy to production only after the development/test installation is verified.
