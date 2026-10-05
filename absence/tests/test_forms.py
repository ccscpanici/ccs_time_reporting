from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from absence.forms import AbsenceRequestForm
from absence.models import AbsenceRequest, PTOAccount

User = get_user_model()


class AbsenceRequestFormTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(username="employee", first_name="Test", last_name="Employee")

    def test_vacation_requires_outlook_calendar_confirmation(self):
        PTOAccount.objects.create(employee=self.employee, vacation_balance_minutes=4800)
        form = AbsenceRequestForm(
            data={
                "absence_type": AbsenceRequest.AbsenceType.VACATION,
                "start_date": "2026-09-21",
                "end_date": "2026-09-25",
            },
            employee=self.employee,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("calendar_acknowledged", form.errors)

    def test_negative_balance_requires_ack_and_full_unpaid_week(self):
        PTOAccount.objects.create(employee=self.employee, vacation_weeks_per_year=1, vacation_used_minutes=7200)
        form = AbsenceRequestForm(
            data={
                "absence_type": AbsenceRequest.AbsenceType.VACATION,
                "start_date": "2026-09-21",
                "end_date": "2026-09-25",
                "calendar_acknowledged": "on",
            },
            employee=self.employee,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("negative_balance_acknowledged", form.errors)
        self.assertIn("unpaid_start_date", form.errors)

        form = AbsenceRequestForm(
            data={
                "absence_type": AbsenceRequest.AbsenceType.VACATION,
                "start_date": "2026-09-21",
                "end_date": "2026-09-25",
                "calendar_acknowledged": "on",
                "negative_balance_acknowledged": "on",
                "unpaid_start_date": "2026-09-28",
                "unpaid_end_date": "2026-10-02",
            },
            employee=self.employee,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_sick_request_does_not_require_calendar_confirmation(self):
        form = AbsenceRequestForm(
            data={
                "absence_type": AbsenceRequest.AbsenceType.SICK,
                "start_date": "2026-09-09",
                "end_date": "2026-09-09",
            },
            employee=self.employee,
        )
        self.assertTrue(form.is_valid(), form.errors)
