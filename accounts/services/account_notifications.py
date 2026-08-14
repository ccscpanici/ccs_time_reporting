import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from accounts.models import AccountNotificationRecipient


logger = logging.getLogger(__name__)


def send_new_account_notification(user):
    """
    Notify all active account notification recipients that a new
    user account has been created.

    Email failures are logged and must never prevent account creation.
    """

    recipients = list(
        AccountNotificationRecipient.objects.filter(active=True)
        .values_list("email", flat=True)
    )

    if not recipients:
        return False

    profile = getattr(user, "employee_profile", None)

    first_name = user.first_name or ""
    last_name = user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()

    office = ""
    if profile is not None:
        office_location = getattr(profile, "office_location", None)
        if office_location is not None:
            office = str(office_location)

    created_at = getattr(user, "date_joined", None) or timezone.now()

    subject_name = full_name or user.username

    subject = f"New Time Reporting Account Created - {subject_name}"

    message_lines = [
        "A new CCS Time Reporting account has been created.",
        "",
        f"Name: {full_name or 'Not provided'}",
        f"Username: {user.username}",
        f"Email: {user.email or 'Not provided'}",
        f"Office: {office or 'Not assigned'}",
        f"Created: {timezone.localtime(created_at):%B %d, %Y at %I:%M %p}",
    ]

    message = "\n".join(message_lines)

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Failed to send new account notification for user %s",
            user.pk,
        )
        return False

    return True
