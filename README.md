# CCS Online Time Reporting

Django starter project for online time reporting, Excel workbook upload/import, direct web editing, PDF/Excel submission, expense tracking, and timesheet submission by email.

## Current design decisions

- Users can create, edit, upload, replace, delete/void, and submit weekly timesheets.
- A user can upload the same week again; the importer replaces the existing week unless it is approved.
- `Expense` has a one-to-one relationship with `TimeEntry`.
- The web editor groups time entries by date, matching the Excel workbook layout.
- Each date defaults to 5 rows, but `Timesheet.entries_per_day` can be increased for web/PDF timesheets.
- The overnight/hotel flag is a date-group value; in Excel it is parsed from the last row of each date group as `True()` or `False()`.
- Excel export only works when each date has 5 or fewer time entries.
- If any date has more than 5 entries, the timesheet must be submitted as a flat PDF report.
- If all dates have 5 or fewer entries, the user can choose Excel Workbook or PDF Report at submit time.
- Submitted timesheets timestamp `submitted_at`, generate the selected attachment, and email it to configured recipients.
- Bootstrap 5.3 is used with CSS-variable based user color schemes.
- Money fields use `django-money` instead of floats.

## Stack

- Django 5.2 LTS-compatible stack
- PostgreSQL-ready, SQLite default for local development
- Bootstrap 5.3.8 CDN
- django-money / py-moneyed
- openpyxl for Excel import/export
- reportlab for flat PDF timesheet reports

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_workcodes
python manage.py runserver
```

Open: http://127.0.0.1:8000/

## Main screens

- `/timesheets/` - list my active timesheets
- `/timesheets/create/` - create a timesheet
- `/timesheets/upload/` - upload `.xlsx`
- `/timesheets/<id>/` - detail page
- `/timesheets/<id>/edit/` - grouped date editor
- `/timesheets/<id>/submit/` - choose Excel/PDF, submit, and email
- `/timesheets/<id>/delete/` - delete/void a timesheet
- `/preferences/` - user color scheme and theme

## Important next steps

The workbook parser has sensible defaults and the known chunk-of-5 structure, but the exact cell mapping should be verified against the final production workbook. See:

- `timesheets/services/workbook_mapping.py`
- `timesheets/services/importer.py`
- `timesheets/services/exporter.py`


## Latest additions

- Users can create a blank weekly timesheet directly on the website using **New Timesheet**.
- The grouped editor renders each date as a section with configurable rows per date.
- Work codes are stored in the database and editable in Django Admin.
- The seed command now includes code `1800 - Employee Development` and creates the `Management Staff` group.
- Submit now timestamps the timesheet and downloads the selected Excel/PDF file. Email automation is intentionally deferred.
- Management reports are available under `/reports/` for users in the `Management Staff` group.
- The first management report is **Employee Billability**, calculated as hours with a job number divided by total worked hours. Management staff are excluded.

Run after migrations:

```bash
python manage.py seed_workcodes
```


## Create / Open Week fix

The create form now renders `entries_per_day`, normalizes any selected date to Monday, creates or opens the user's weekly timesheet, and redirects directly to the grouped edit screen.

## Latest patch notes

- Timesheet job entry is now a free-text Job # field instead of a required dropdown.
- If a typed job number matches an existing Job record, the row also links to that Job for reporting/admin use.
- PDF submissions are generated with ReportLab and returned with `application/pdf` content type.
- Timesheet creation now requires the selected week start date to be a Sunday.
- Imported workbook dates are normalized to Sunday-based work weeks.


## Mileage rates

Mileage rates are stored in the database in the `MileageRate` model and are editable in Django Admin.
The seed command loads yearly rates from 2000 through 2026, including 2026 at `0.720`.
When a timesheet is created, the application snapshots the mileage rate for the year of the week start.
If that year is missing, the latest available mileage rate is used.

```bash
python manage.py seed_workcodes
```

This command seeds work codes, mileage rates, and the Management Staff group.


## Submission artifacts

When a user clicks **Submit and Download**, the app generates the selected Excel workbook or PDF report, stores a historical copy in `TimesheetSubmissionArtifact.file`, timestamps the timesheet, and streams that saved file back to the browser.

## Regenerated update notes

This regenerated package includes:
- User Profile page at `/profile/`
- Office Location dropdown on the user profile
- Home address fields on the user profile
- PDF margins increased to 0.5 inch left/right/top/bottom
- Latest uploaded `2026_Timesheet.xlsx` template included

Run the seed command after migrating to populate offices, work codes, mileage rates, and Management Staff group:

```bash
python manage.py seed_all
```
