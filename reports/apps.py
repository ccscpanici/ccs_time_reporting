"""Application support code for apps."""


from django.apps import AppConfig


class ReportsConfig(AppConfig):
    """Provide reports config behavior for this module."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "reports"
