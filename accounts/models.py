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
