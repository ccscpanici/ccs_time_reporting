"""Application support code for apps."""

from django.apps import AppConfig


class AbsenceConfig(AppConfig):
    """Provide absence config behavior for this module."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "absence"
    verbose_name = "Absence Management"
