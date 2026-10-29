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
