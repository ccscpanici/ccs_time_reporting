from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.urls import reverse
from djmoney.models.fields import MoneyField
from djmoney.money import Money


class Customer(models.Model):
    name = models.CharField(max_length=255, unique=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Job(models.Model):
    job_number = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="jobs", null=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.job_number} {self.description}".strip()


class WorkCode(models.Model):
    code = models.CharField(max_length=20, unique=True)
    description = models.CharField(max_length=255)
    allows_overtime = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "code"]

    def __str__(self):
        return f"{self.code} - {self.description}"


class MileageRate(models.Model):
    year = models.PositiveIntegerField(unique=True)
    rate = models.DecimalField(max_digits=6, decimal_places=3)

    class Meta:
        ordering = ["-year"]

    def __str__(self):
        return f"{self.year}: {self.rate}"

    @classmethod
    def rate_for_date(cls, work_date):
        exact = cls.objects.filter(year=work_date.year).first()
        if exact:
            return exact.rate
        latest = cls.objects.order_by("-year").first()
        if latest:
            return latest.rate
        return Decimal("0.720")


class Timesheet(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        REOPENED = "reopened", "Reopened"
        APPROVED = "approved", "Approved"
        INVOICED = "invoiced", "Invoiced"
        REJECTED = "rejected", "Rejected"
        VOID = "void", "Voided"

    class ExportFormat(models.TextChoices):
        EXCEL = "excel", "Excel Workbook"
        PDF = "pdf", "PDF Report"

    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="timesheets")
    week_start = models.DateField()
    entries_per_day = models.PositiveSmallIntegerField(default=5)
    template_entries_per_day = models.PositiveSmallIntegerField(default=5)
    # Snapshot of the yearly mileage reimbursement rate used for this timesheet.
    # Populated from MileageRate based on week_start when the timesheet is created.
    mileage_rate = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal("0.720"))

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submitted_timesheets",
    )
    submission_export_format = models.CharField(
        max_length=20,
        choices=ExportFormat.choices,
        blank=True,
    )

    reopened_at = models.DateTimeField(null=True, blank=True)
    reopened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reopened_timesheets",
    )
    reopen_reason = models.TextField(blank=True)

    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_timesheets",
    )

    invoiced_at = models.DateTimeField(null=True, blank=True)
    invoiced_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoiced_timesheets",
    )

    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="deleted_timesheets",
    )
    delete_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["employee", "week_start"], name="unique_employee_week_timesheet")]
        ordering = ["-week_start", "-created_at"]

    def __str__(self):
        return f"{self.employee} - week of {self.week_start}"

    def get_absolute_url(self):
        return reverse("timesheet_detail", args=[self.pk])

    @property
    def can_edit(self):
        return self.deleted_at is None and self.status in {self.Status.DRAFT, self.Status.REJECTED, self.Status.REOPENED}

    @property
    def can_submit(self):
        return self.deleted_at is None and self.status in {self.Status.DRAFT, self.Status.REJECTED, self.Status.REOPENED}

    @property
    def can_reopen(self):
        return self.deleted_at is None and self.status == self.Status.SUBMITTED

    @property
    def is_locked(self):
        return self.deleted_at is not None or self.status in {self.Status.SUBMITTED, self.Status.APPROVED, self.Status.INVOICED, self.Status.VOID}

    @property
    def week_dates(self):
        return [self.week_start + timedelta(days=offset) for offset in range(7)]

    def entry_count_for_date(self, work_date):
        return self.entries.filter(work_date=work_date).count()

    @property
    def has_excel_overflow(self):
        return any(self.entry_count_for_date(work_date) > self.template_entries_per_day for work_date in self.week_dates)

    @property
    def can_export_excel(self):
        return not self.has_excel_overflow


class TimeEntry(models.Model):
    timesheet = models.ForeignKey(Timesheet, on_delete=models.CASCADE, related_name="entries")
    work_date = models.DateField()
    row_order = models.PositiveSmallIntegerField(default=1)
    # Free-text job number as entered on the timesheet. This mirrors the Excel template
    # and lets users enter ad-hoc job numbers without first creating a Job record.
    job_number = models.CharField(max_length=50, blank=True)
    # Optional normalized Job link for admin/reporting lookups when the job already exists.
    job = models.ForeignKey(Job, on_delete=models.PROTECT, null=True, blank=True)
    work_code = models.ForeignKey(WorkCode, on_delete=models.PROTECT, null=True, blank=True)
    regular_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    overtime_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    doubletime_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    overnight_stay = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["work_date", "row_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["timesheet", "work_date", "row_order"],
                name="unique_timesheet_day_row",
            )
        ]

    @property
    def total_hours(self):
        return self.regular_hours + self.overtime_hours + self.doubletime_hours

    @property
    def job_display(self):
        if self.job_number:
            return self.job_number
        if self.job_id:
            return self.job.job_number
        return ""


class Expense(models.Model):
    time_entry = models.OneToOneField(TimeEntry, on_delete=models.CASCADE, related_name="expense")

    # Editable quantity. The dollar mileage reimbursement is calculated automatically
    # from miles * timesheet.mileage_rate and is not user editable.
    miles = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    mileage = MoneyField(max_digits=10, decimal_places=2, default_currency="USD", default=0, editable=False)

    per_diem_food = MoneyField(max_digits=10, decimal_places=2, default_currency="USD", default=0)
    air_fare = MoneyField(max_digits=10, decimal_places=2, default_currency="USD", default=0)
    hotel = MoneyField(max_digits=10, decimal_places=2, default_currency="USD", default=0)
    tolls_parking = MoneyField(max_digits=10, decimal_places=2, default_currency="USD", default=0)
    rental_car_fuel = MoneyField(max_digits=10, decimal_places=2, default_currency="USD", default=0)
    business_meals = MoneyField(max_digits=10, decimal_places=2, default_currency="USD", default=0)
    other_expense = MoneyField(max_digits=10, decimal_places=2, default_currency="USD", default=0)
    explanation_of_expenses = models.TextField(blank=True)

    def calculate_mileage(self):
        rate = self.time_entry.timesheet.mileage_rate or Decimal("0.720")
        return Money((self.miles or Decimal("0")) * rate, "USD")

    @property
    def daily_total(self):
        return (
            self.mileage
            + self.per_diem_food
            + self.air_fare
            + self.hotel
            + self.tolls_parking
            + self.rental_car_fuel
            + self.business_meals
            + self.other_expense
        )

    def save(self, *args, **kwargs):
        self.mileage = self.calculate_mileage()
        super().save(*args, **kwargs)



class PartEntry(models.Model):
    time_entry = models.OneToOneField(
        TimeEntry,
        on_delete=models.CASCADE,
        related_name="part_entry",
        null=True,
        blank=True,
    )

    ee_stock_job_number = models.CharField(max_length=100, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    part_description_part_number = models.CharField(max_length=255, blank=True)
    additional_notes_for_customer = models.TextField(blank=True)
    reorder_part = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Part entry"
        verbose_name_plural = "Part entries"

    def __str__(self):
        return f"{self.job_display} - {self.part_description_part_number}".strip(" -")

    @property
    def job_display(self):
        if self.ee_stock_job_number:
            return self.ee_stock_job_number
        if self.time_entry_id:
            return self.time_entry.job_display
        return ""

    @property
    def work_date(self):
        return self.time_entry.work_date if self.time_entry_id else None




class TimesheetReceipt(models.Model):
    timesheet = models.ForeignKey(
        Timesheet,
        on_delete=models.CASCADE,
        related_name="receipts",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_timesheet_receipts",
    )
    file = models.FileField(upload_to="timesheet_receipts/%Y/%m/")
    original_filename = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.original_filename

    def filename(self):
        return self.original_filename or self.file.name.split("/")[-1]


class TimesheetSubmissionArtifact(models.Model):
    class FileType(models.TextChoices):
        EXCEL = "xlsx", "Excel Workbook"
        PDF = "pdf", "PDF Report"

    timesheet = models.ForeignKey(Timesheet, on_delete=models.CASCADE, related_name="submission_artifacts")
    file = models.FileField(upload_to="timesheet_submissions/")
    file_type = models.CharField(max_length=10, choices=FileType.choices)
    export_format = models.CharField(max_length=20, choices=Timesheet.ExportFormat.choices)
    # True when this artifact was generated as part of the official Submit and Download flow.
    # False when the user simply downloaded a draft/reopened/submitted timesheet copy.
    submitted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_timesheet_artifacts",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.timesheet} - {self.file_type} - {self.created_at:%Y-%m-%d %H:%M}"

class TimesheetImport(models.Model):
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="timesheet_imports")
    uploaded_file = models.FileField(upload_to="timesheet_uploads/")
    imported_timesheet = models.ForeignKey(Timesheet, on_delete=models.SET_NULL, null=True, blank=True)
    imported_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=30, default="pending")
    message = models.TextField(blank=True)


class TimesheetSubmissionRecipient(models.Model):
    email = models.EmailField(unique=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.email


class BulkImportJob(models.Model):
    STATUS_CHOICES = [("pending","Pending"),("running","Running"),("completed","Completed"),("failed","Failed")]

    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bulk_import_jobs")
    uploaded_zip = models.FileField(upload_to="bulk_imports/")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    total_files = models.PositiveIntegerField(default=0)
    processed_files = models.PositiveIntegerField(default=0)
    imported_files = models.PositiveIntegerField(default=0)
    failed_files = models.PositiveIntegerField(default=0)
    results_json = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
