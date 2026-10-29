"""Signal handlers for account notifications and employee financial profiles."""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import EmployeeFinancialProfile, EmployeeProfile
from accounts.services.account_notifications import send_new_account_notification


User = get_user_model()


@receiver(post_save, sender=User)
def notify_new_account_created(sender, instance, created, **kwargs):
    """Notify administrators when a new user is created, unless suppressed."""
    if not created:
        return

    if getattr(instance, "_suppress_account_notification", False):
        return

    send_new_account_notification(instance)


@receiver(post_save, sender=EmployeeProfile)
def ensure_employee_financial_profile(sender, instance, created, **kwargs):
    """Create a financial profile without changing existing financial data."""
    if not created:
        return

    EmployeeFinancialProfile.objects.get_or_create(employee=instance)
