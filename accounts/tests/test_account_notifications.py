from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from accounts.models import AccountNotificationRecipient
from accounts.services.account_notifications import (
    send_new_account_notification,
)


User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="timetrack@gotoccs.com",
)
class AccountNotificationTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="jdoe",
            email="jdoe@gotoccs.com",
            first_name="John",
            last_name="Doe",
            password="test-password",
        )

    def test_active_recipient_receives_notification(self):
        AccountNotificationRecipient.objects.create(
            name="Chris",
            email="chris@gotoccs.com",
            active=True,
        )

        result = send_new_account_notification(self.user)

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]

        self.assertIn("chris@gotoccs.com", email.to)
        self.assertIn("John Doe", email.subject)
        self.assertIn("Username: jdoe", email.body)
        self.assertIn("Email: jdoe@gotoccs.com", email.body)

    def test_all_active_recipients_receive_notification(self):
        AccountNotificationRecipient.objects.create(
            email="first@gotoccs.com",
            active=True,
        )
        AccountNotificationRecipient.objects.create(
            email="second@gotoccs.com",
            active=True,
        )

        send_new_account_notification(self.user)

        self.assertEqual(len(mail.outbox), 1)

        self.assertCountEqual(
            mail.outbox[0].to,
            [
                "first@gotoccs.com",
                "second@gotoccs.com",
            ],
        )

    def test_inactive_recipient_does_not_receive_notification(self):
        AccountNotificationRecipient.objects.create(
            email="active@gotoccs.com",
            active=True,
        )
        AccountNotificationRecipient.objects.create(
            email="inactive@gotoccs.com",
            active=False,
        )

        send_new_account_notification(self.user)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].to,
            ["active@gotoccs.com"],
        )

    def test_no_recipients_does_not_send_email(self):
        result = send_new_account_notification(self.user)

        self.assertFalse(result)
        self.assertEqual(len(mail.outbox), 0)

    @patch("accounts.services.account_notifications.send_mail")
    def test_email_failure_does_not_raise_exception(self, mock_send_mail):
        AccountNotificationRecipient.objects.create(
            email="admin@gotoccs.com",
            active=True,
        )

        mock_send_mail.side_effect = RuntimeError("SMTP unavailable")

        result = send_new_account_notification(self.user)

        self.assertFalse(result)

    def test_notification_contains_user_information(self):
        AccountNotificationRecipient.objects.create(
            email="admin@gotoccs.com",
            active=True,
        )

        send_new_account_notification(self.user)

        body = mail.outbox[0].body

        self.assertIn("Name: John Doe", body)
        self.assertIn("Username: jdoe", body)
        self.assertIn("Email: jdoe@gotoccs.com", body)
        self.assertIn("Created:", body)

    def test_creating_user_automatically_sends_notification(self):
        AccountNotificationRecipient.objects.create(
            email="admin@gotoccs.com",
            active=True,
        )

        User.objects.create_user(
            username="newuser",
            email="newuser@gotoccs.com",
            first_name="New",
            last_name="User",
            password="test-password",
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("New User", mail.outbox[0].subject)
        self.assertIn("Username: newuser", mail.outbox[0].body)


    def test_editing_existing_user_does_not_send_notification(self):
        AccountNotificationRecipient.objects.create(
            email="admin@gotoccs.com",
            active=True,
        )

        user = User.objects.create_user(
            username="existinguser",
            email="existing@gotoccs.com",
            password="test-password",
        )

        mail.outbox.clear()

        user.first_name = "Updated"
        user.save()

        self.assertEqual(len(mail.outbox), 0)
