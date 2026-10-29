"""Application support code for models."""

from django.conf import settings
from django.db import models


class OfficeLocation(models.Model):
    """Provide office location behavior for this module."""
    name = models.CharField(max_length=100, unique=True)
    address_1 = models.CharField(max_length=255)
    address_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=50)
    postal_code = models.CharField(max_length=20)
    active = models.BooleanField(default=True)

    class Meta:
        """Provide meta behavior for this module."""
        ordering = ["name"]

    @property
    def address_line(self):
        """Provide the address line operation for this module."""
        return f"{self.address_1} {self.address_2}".strip()

    @property
    def city_state_zip(self):
        """Provide the city state zip operation for this module."""
        return f"{self.city}, {self.state} {self.postal_code}".strip()

    def __str__(self):
        """Provide the str operation for this module."""
        return self.name


class EmployeeProfile(models.Model):
    """Provide employee profile behavior for this module."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='employee_profile')
    employee_code = models.CharField(max_length=30, blank=True, unique=True, null=True)
    title = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    birthday = models.DateField(null=True, blank=True, help_text="Optional employee date of birth; visible to authorized administrators.")
    office_location = models.ForeignKey(
        OfficeLocation,
        on_delete=models.PROTECT,
        related_name="employees",
        null=True,
        blank=True,
        help_text="Company office this employee is assigned to.",
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_reports",
        limit_choices_to={"groups__name": "ProjectManagers"},
        help_text="Project manager responsible for approving this employee's timesheets.",
    )

    # Employee home address used for timesheet export header fields.
    address_1 = models.CharField(max_length=255, blank=True)
    address_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=50, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default="USA", blank=True)


    @property
    def address_line(self):
        """Provide the address line operation for this module."""
        return f"{self.address_1} {self.address_2}".strip()

    @property
    def city_state_zip(self):
        """Provide the city state zip operation for this module."""
        parts = [self.city, self.state, self.postal_code]
        if not any(parts):
            return ""
        return f"{self.city}, {self.state} {self.postal_code}".strip()

    def __str__(self):
        """Provide the str operation for this module."""
        return self.user.get_full_name() or self.user.get_username()

class UserPreference(models.Model):
    """Provide user preference behavior for this module."""
    class ColorScheme(models.TextChoices):
        """Provide color scheme behavior for this module."""
        DEFAULT = 'default', 'Default Blue'
        SLATE = 'slate', 'Slate'
        FOREST = 'forest', 'Forest'
        CRIMSON = 'crimson', 'Crimson'
        GOLD = 'gold', 'Gold'

    class Theme(models.TextChoices):
        """Provide theme behavior for this module."""
        AUTO = 'auto', 'Auto'
        LIGHT = 'light', 'Light'
        DARK = 'dark', 'Dark'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='preferences')
    color_scheme = models.CharField(max_length=20, choices=ColorScheme.choices, default=ColorScheme.DEFAULT)
    theme = models.CharField(max_length=10, choices=Theme.choices, default=Theme.AUTO)

    def __str__(self):
        """Provide the str operation for this module."""
        return f'{self.user} preferences'

class AccountNotificationRecipient(models.Model):
    """Provide account notification recipient behavior for this module."""
    name = models.CharField(
        max_length=150,
        blank=True,
        help_text="Optional name for this notification recipient.",
    )
    email = models.EmailField(unique=True)
    active = models.BooleanField(default=True)

    class Meta:
        """Provide meta behavior for this module."""
        ordering = ["email"]
        verbose_name = "Account Notification Recipient"
        verbose_name_plural = "Account Notification Recipients"

    def __str__(self):
        """Provide the str operation for this module."""
        if self.name:
            return f"{self.name} <{self.email}>"
        return self.email

class CompanyOverhead(models.Model):
    """A recurring company expense included in annualized overhead."""

    class Frequency(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        ANNUAL = "annual", "Annual"

    name = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    frequency = models.CharField(max_length=10, choices=Frequency.choices, default=Frequency.MONTHLY)
    effective_start = models.DateField()
    effective_end = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name", "-effective_start", "pk"]
        verbose_name = "Company Overhead"
        verbose_name_plural = "Company Overhead"
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gte=0), name="accounts_overhead_nonnegative"),
            models.CheckConstraint(
                condition=models.Q(effective_end__isnull=True) | models.Q(effective_end__gte=models.F("effective_start")),
                name="accounts_overhead_valid_dates",
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if self.amount is not None and self.amount < 0:
            raise ValidationError({"amount": "Amount cannot be negative."})
        if self.effective_start and self.effective_end and self.effective_end < self.effective_start:
            raise ValidationError({"effective_end": "End date cannot precede start date."})

    @property
    def annual_amount(self):
        return self.amount * (12 if self.frequency == self.Frequency.MONTHLY else 1)

    @classmethod
    def annual_total_on(cls, on_date):
        """Annualized run-rate for expenses active on a given date."""
        from decimal import Decimal
        expenses = cls.objects.filter(
            active=True, effective_start__lte=on_date
        ).filter(models.Q(effective_end__isnull=True) | models.Q(effective_end__gte=on_date))
        return sum((item.annual_amount for item in expenses), Decimal("0.00"))

    def __str__(self):
        return self.name


class EmployeeFinancialProfile(models.Model):
    """Restricted financial assumptions used for current employee burn rates."""

    employee = models.OneToOneField(
        EmployeeProfile, on_delete=models.CASCADE, related_name="financial_profile"
    )
    annual_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    employer_payroll_taxes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    annual_benefits = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    employer_401k = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    annual_bonuses = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_annual_costs = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    include_in_overhead = models.BooleanField(default=True)
    annual_working_hours = models.DecimalField(max_digits=8, decimal_places=2, default=2080)
    customer_billing_rate = models.DecimalField(max_digits=9, decimal_places=2, default=140)

    class Meta:
        verbose_name = "Employee Financial Profile"
        verbose_name_plural = "Employee Financial Profiles"
        constraints = [
            models.CheckConstraint(condition=models.Q(**{field + "__gte": 0}), name="acct_fin_" + {"annual_salary":"salary", "employer_payroll_taxes":"taxes", "annual_benefits":"benefits", "employer_401k":"401k", "annual_bonuses":"bonus", "other_annual_costs":"other", "customer_billing_rate":"billing"}[field] + "_gte0")
            for field in ("annual_salary", "employer_payroll_taxes", "annual_benefits", "employer_401k", "annual_bonuses", "other_annual_costs", "customer_billing_rate")
        ] + [
            models.CheckConstraint(condition=models.Q(annual_working_hours__gt=0), name="acct_fin_hours_gt0")
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        errors = {}
        for field in ("annual_salary", "employer_payroll_taxes", "annual_benefits", "employer_401k", "annual_bonuses", "other_annual_costs", "customer_billing_rate"):
            value = getattr(self, field)
            if value is not None and value < 0:
                errors[field] = "Cannot be negative."
        if self.annual_working_hours is not None and self.annual_working_hours <= 0:
            errors["annual_working_hours"] = "Must be greater than zero."
        if errors:
            raise ValidationError(errors)

    @property
    def direct_annual_cost(self):
        return sum((getattr(self, field) for field in (
            "annual_salary", "employer_payroll_taxes", "annual_benefits",
            "employer_401k", "annual_bonuses", "other_annual_costs"
        )), __import__("decimal").Decimal("0.00"))

    def allocated_annual_overhead_on(self, on_date):
        from decimal import Decimal
        if not self.include_in_overhead or not self.employee.user.is_active:
            return Decimal("0.00")
        eligible = type(self).objects.filter(include_in_overhead=True, employee__user__is_active=True).count()
        if not eligible:
            return Decimal("0.00")
        return (CompanyOverhead.annual_total_on(on_date) / Decimal(eligible)).quantize(Decimal("0.01"))

    def total_annual_cost_on(self, on_date):
        return self.direct_annual_cost + self.allocated_annual_overhead_on(on_date)

    def burn_rate_on(self, on_date):
        from decimal import Decimal
        return (self.total_annual_cost_on(on_date) / self.annual_working_hours).quantize(Decimal("0.01"))

    def __str__(self):
        return str(self.employee)
