from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class PTOAccount(models.Model):
    """Current PTO snapshot for an employee.

    Balances are stored as signed integer minutes so source values such as
    73:01 and -26:16 can be represented exactly.
    """

    employee = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pto_account",
    )
    vacation_weeks_per_year = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    vacation_balance_minutes = models.IntegerField(default=0)
    sick_balance_minutes = models.IntegerField(default=0)
    vacation_used_minutes = models.IntegerField(default=0)
    sick_used_minutes = models.IntegerField(default=0)
    balance_as_of = models.DateField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pto_accounts_updated",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("employee__last_name", "employee__first_name", "employee__username")
        verbose_name = "PTO Account"
        verbose_name_plural = "PTO Accounts"

    def __str__(self):
        name = self.employee.get_full_name() or self.employee.get_username()
        return f"PTO - {name}"

    @property
    def vacation_accrual_minutes(self):
        """Payroll report's ``Vacation Available`` value.

        CCS uses this as an accrual/reference value, not as remaining vacation.
        The legacy database field name is retained to avoid a destructive rename.
        """

        return self.vacation_balance_minutes

    @property
    def sick_available_minutes(self):
        """Payroll-reported sick value; negative values are expected at CCS."""

        return self.sick_balance_minutes

    @property
    def annual_vacation_minutes(self):
        from absence.services.pto_balances import annual_vacation_minutes

        return annual_vacation_minutes(self.vacation_weeks_per_year)

    @property
    def calculated_vacation_balance_minutes(self):
        return self.annual_vacation_minutes - self.vacation_used_minutes

    def approved_vacation_pending_minutes(self, *, as_of=None):
        from absence.services.pto_balances import approved_vacation_pending_minutes

        return approved_vacation_pending_minutes(self.employee, as_of=as_of)

    def projected_vacation_balance_minutes(self, *, as_of=None):
        return (
            self.calculated_vacation_balance_minutes
            - self.approved_vacation_pending_minutes(as_of=as_of)
        )


class PTOImport(models.Model):
    class Status(models.TextChoices):
        PREVIEW = "preview", "Preview"
        APPLIED = "applied", "Applied"
        FAILED = "failed", "Failed"

    source_file = models.FileField(upload_to="absence/pto_imports/%Y/%m/")
    source_name = models.CharField(max_length=255)
    report_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PREVIEW)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pto_imports_uploaded",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pto_imports_applied",
    )
    applied_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ("-uploaded_at",)

    def __str__(self):
        return f"{self.source_name} ({self.get_status_display()})"


class PTOImportRow(models.Model):
    class MatchStatus(models.TextChoices):
        MATCHED = "matched", "Matched"
        UNMATCHED = "unmatched", "Unmatched"
        AMBIGUOUS = "ambiguous", "Ambiguous"
        INVALID = "invalid", "Invalid"

    pto_import = models.ForeignKey(PTOImport, on_delete=models.CASCADE, related_name="rows")
    row_number = models.PositiveIntegerField()
    employee_name = models.CharField(max_length=200)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pto_import_rows",
    )
    match_status = models.CharField(max_length=20, choices=MatchStatus.choices)
    match_message = models.CharField(max_length=255, blank=True)
    sick_available_minutes = models.IntegerField(default=0)
    sick_used_minutes = models.IntegerField(default=0)
    vacation_available_minutes = models.IntegerField(default=0)
    vacation_used_minutes = models.IntegerField(default=0)

    class Meta:
        ordering = ("row_number",)
        constraints = [
            models.UniqueConstraint(fields=("pto_import", "row_number"), name="absence_unique_pto_import_row")
        ]

    def __str__(self):
        return f"{self.employee_name} - {self.get_match_status_display()}"


class PTOAccountChange(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        IMPORT = "import", "PTO Report Import"

    pto_account = models.ForeignKey(PTOAccount, on_delete=models.CASCADE, related_name="changes")
    pto_import = models.ForeignKey(
        PTOImport,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="account_changes",
    )
    source = models.CharField(max_length=20, choices=Source.choices)

    old_vacation_weeks_per_year = models.DecimalField(max_digits=5, decimal_places=2)
    new_vacation_weeks_per_year = models.DecimalField(max_digits=5, decimal_places=2)
    old_vacation_balance_minutes = models.IntegerField()
    new_vacation_balance_minutes = models.IntegerField()
    old_sick_balance_minutes = models.IntegerField()
    new_sick_balance_minutes = models.IntegerField()
    old_vacation_used_minutes = models.IntegerField()
    new_vacation_used_minutes = models.IntegerField()
    old_sick_used_minutes = models.IntegerField()
    new_sick_used_minutes = models.IntegerField()
    old_balance_as_of = models.DateField(null=True, blank=True)
    new_balance_as_of = models.DateField(null=True, blank=True)

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="pto_account_changes",
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ("-changed_at",)

    def __str__(self):
        return f"{self.pto_account} - {self.get_source_display()} - {self.changed_at:%Y-%m-%d}"


class AbsenceRequest(models.Model):
    MIN_VACATION_BALANCE_MINUTES = -40 * 60
    WORKDAY_MINUTES = 8 * 60

    class AbsenceType(models.TextChoices):
        VACATION = "vacation", "Vacation"
        SICK = "sick", "Sick"
        PERSONAL = "personal", "Personal Time"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Pending Supervisor Approval"
        PENDING_EXCEPTION = "pending_exception", "Pending Negative Balance Exception Approval"
        APPROVED = "approved", "Approved"
        DENIED = "denied", "Denied"

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="absence_requests",
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_absence_requests",
        help_text="Supervisor snapshot captured when the request is submitted.",
    )
    absence_type = models.CharField(max_length=20, choices=AbsenceType.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    requested_minutes = models.PositiveIntegerField(default=0)
    calendar_acknowledged = models.BooleanField(default=False)
    late_notice = models.BooleanField(default=False)

    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="absence_requests_submitted",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    vacation_weeks_per_year_snapshot = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    vacation_balance_snapshot_minutes = models.IntegerField(default=0)
    sick_balance_snapshot_minutes = models.IntegerField(default=0)
    balance_as_of_snapshot = models.DateField(null=True, blank=True)
    projected_vacation_balance_minutes = models.IntegerField(null=True, blank=True)

    negative_balance_exception_required = models.BooleanField(default=False)
    negative_balance_acknowledged = models.BooleanField(default=False)
    unpaid_start_date = models.DateField(null=True, blank=True)
    unpaid_end_date = models.DateField(null=True, blank=True)

    supervisor_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="absence_requests_supervisor_approved",
    )
    supervisor_approved_at = models.DateTimeField(null=True, blank=True)
    supervisor_denied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="absence_requests_supervisor_denied",
    )
    supervisor_denied_at = models.DateTimeField(null=True, blank=True)
    supervisor_notes = models.TextField(blank=True)

    exception_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="absence_requests_exception_approved",
    )
    exception_approved_at = models.DateTimeField(null=True, blank=True)
    exception_denied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="absence_requests_exception_denied",
    )
    exception_denied_at = models.DateTimeField(null=True, blank=True)
    exception_notes = models.TextField(blank=True)

    finalized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-start_date", "-created_at")
        indexes = [
            models.Index(fields=("status", "manager"), name="absence_status_mgr_idx"),
            models.Index(fields=("employee", "start_date"), name="absence_employee_date_idx"),
        ]

    def __str__(self):
        employee = self.employee.get_full_name() or self.employee.get_username()
        return f"{employee} - {self.get_absence_type_display()} - {self.start_date:%Y-%m-%d}"

    @property
    def is_final(self):
        return self.status in {self.Status.APPROVED, self.Status.DENIED}

    @property
    def annual_vacation_snapshot_minutes(self):
        from absence.services.pto_balances import annual_vacation_minutes

        return annual_vacation_minutes(self.vacation_weeks_per_year_snapshot)

    @property
    def vacation_used_snapshot_minutes(self):
        return self.annual_vacation_snapshot_minutes - self.vacation_balance_snapshot_minutes

    @property
    def approved_vacation_pending_snapshot_minutes(self):
        if self.projected_vacation_balance_minutes is None:
            return 0
        return max(
            0,
            self.vacation_balance_snapshot_minutes
            - self.requested_minutes
            - self.projected_vacation_balance_minutes,
        )


class AbsenceRequestDay(models.Model):
    request = models.ForeignKey(
        AbsenceRequest,
        on_delete=models.CASCADE,
        related_name="days",
    )
    work_date = models.DateField()
    requested_minutes = models.PositiveIntegerField(default=AbsenceRequest.WORKDAY_MINUTES)

    class Meta:
        ordering = ("work_date",)
        constraints = [
            models.UniqueConstraint(
                fields=("request", "work_date"),
                name="absence_unique_request_work_date",
            )
        ]

    def __str__(self):
        return f"{self.request} - {self.work_date:%Y-%m-%d}"


class AbsenceArtifact(models.Model):
    class ArtifactType(models.TextChoices):
        FINAL_PDF = "final_pdf", "Final PDF"

    request = models.ForeignKey(AbsenceRequest, on_delete=models.CASCADE, related_name="artifacts")
    artifact_type = models.CharField(max_length=20, choices=ArtifactType.choices, default=ArtifactType.FINAL_PDF)
    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=1000)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="absence_artifacts_generated",
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    sha256 = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ("-generated_at",)

    def __str__(self):
        return self.filename

    @property
    def path(self):
        return Path(self.file_path)
