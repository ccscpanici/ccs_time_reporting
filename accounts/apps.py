"""Application support code for apps."""

from django.apps import AppConfig

class AccountsConfig(AppConfig):
    """Provide accounts config behavior for this module."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        """Provide the ready operation for this module."""
        import accounts.signals  # noqa: F401
