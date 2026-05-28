from django.conf import settings
from django.db import models


class OfficeLocation(models.Model):
    name = models.CharField(max_length=100, unique=True)
    address_1 = models.CharField(max_length=255)
    address_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=50)
    postal_code = models.CharField(max_length=20)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    @property
    def address_line(self):
        return f"{self.address_1} {self.address_2}".strip()

    @property
    def city_state_zip(self):
        return f"{self.city}, {self.state} {self.postal_code}".strip()

    def __str__(self):
        return self.name


class EmployeeProfile(models.Model):
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
        return f"{self.address_1} {self.address_2}".strip()

    @property
    def city_state_zip(self):
        parts = [self.city, self.state, self.postal_code]
        if not any(parts):
            return ""
        return f"{self.city}, {self.state} {self.postal_code}".strip()

    def __str__(self):
        return self.user.get_full_name() or self.user.get_username()

class UserPreference(models.Model):
    class ColorScheme(models.TextChoices):
        DEFAULT = 'default', 'Default Blue'
        SLATE = 'slate', 'Slate'
        FOREST = 'forest', 'Forest'
        CRIMSON = 'crimson', 'Crimson'
        GOLD = 'gold', 'Gold'

    class Theme(models.TextChoices):
        AUTO = 'auto', 'Auto'
        LIGHT = 'light', 'Light'
        DARK = 'dark', 'Dark'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='preferences')
    color_scheme = models.CharField(max_length=20, choices=ColorScheme.choices, default=ColorScheme.DEFAULT)
    theme = models.CharField(max_length=10, choices=Theme.choices, default=Theme.AUTO)

    def __str__(self):
        return f'{self.user} preferences'
