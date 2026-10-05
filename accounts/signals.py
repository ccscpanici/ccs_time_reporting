"""Application support code for signals."""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.services.account_notifications import (
    send_new_account_notification,
)


User = get_user_model()


@receiver(post_save, sender=User)
def notify_new_account_created(sender, instance, created, **kwargs):
    """Provide the notify new account created operation for this module."""
    if not created:
        return

    if getattr(instance, "_suppress_account_notification", False):
        return

    send_new_account_notification(instance)
