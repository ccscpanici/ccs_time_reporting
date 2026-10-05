from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from absence.models import AbsenceRequest, AbsenceRequestDay, PTOAccount
from absence.services.pto_balances import (
    PAY_PERIOD_ANCHOR_END,
    approved_vacation_pending_minutes,
    pay_period_end_for,
    pending_expiration_for,
    vacation_summary,
)

User = get_user_model()


class PTOPayPeriodTests(TestCase):
    def test_anchor_and_biweekly_period_ends(self):
        self.assertEqual(PAY_PERIOD_ANCHOR_END, date(2026, 9, 11))
        self.assertEqual(pay_period_end_for(date(2026, 9, 8)), date(2026, 9, 11))
        self.assertEqual(pay_period_end_for(date(2026, 9, 18)), date(2026, 9, 25))
        self.assertEqual(pay_period_end_for(date(2026, 10, 1)), date(2026, 10, 9))

    def test_pending_expires_after_following_pay_period(self):
        self.assertEqual(pending_expiration_for(date(2026, 9, 8)), date(2026, 9, 25))
        self.assertEqual(pending_expiration_for(date(2026, 9, 18)), date(2026, 10, 9))


class VacationSummaryTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(
            username="employee",
            first_name="Test",
            last_name="Employee",
        )
        self.account = PTOAccount.objects.create(
            employee=self.employee,
            vacation_weeks_per_year=3,
            vacation_balance_minutes=4381,
            vacation_used_minutes=3780,
            sick_balance_minutes=-6540,
            sick_used_minutes=1050,
            balance_as_of=date(2026, 9, 8),
        )

    def test_vacation_balance_uses_entitlement_minus_payroll_used(self):
        summary = vacation_summary(self.account, as_of=date(2026, 9, 8))

        self.assertEqual(summary.annual_entitlement_minutes, 7200)
        self.assertEqual(summary.vacation_accrual_minutes, 4381)
        self.assertEqual(summary.vacation_used_minutes, 3780)
        self.assertEqual(summary.vacation_balance_minutes, 3420)

    def test_approved_vacation_pending_is_calculated_per_workday(self):
        AbsenceRequest.objects.create(
            employee=self.employee,
            absence_type=AbsenceRequest.AbsenceType.VACATION,
            start_date=date(2026, 9, 8),
            end_date=date(2026, 9, 10),
            requested_minutes=1440,
            calendar_acknowledged=True,
            status=AbsenceRequest.Status.APPROVED,
        )

        self.assertEqual(
            approved_vacation_pending_minutes(self.employee, as_of=date(2026, 9, 25)),
            1440,
        )
        self.assertEqual(
            approved_vacation_pending_minutes(self.employee, as_of=date(2026, 9, 26)),
            0,
        )


    def test_approved_pending_uses_actual_partial_day_hours(self):
        request = AbsenceRequest.objects.create(
            employee=self.employee,
            absence_type=AbsenceRequest.AbsenceType.VACATION,
            start_date=date(2026, 9, 21),
            end_date=date(2026, 9, 22),
            requested_minutes=720,
            calendar_acknowledged=True,
            status=AbsenceRequest.Status.APPROVED,
        )
        AbsenceRequestDay.objects.create(
            request=request,
            work_date=date(2026, 9, 21),
            requested_minutes=240,
        )
        AbsenceRequestDay.objects.create(
            request=request,
            work_date=date(2026, 9, 22),
            requested_minutes=480,
        )

        self.assertEqual(
            approved_vacation_pending_minutes(self.employee, as_of=date(2026, 9, 25)),
            720,
        )

    def test_projected_balance_subtracts_approved_pending(self):
        AbsenceRequest.objects.create(
            employee=self.employee,
            absence_type=AbsenceRequest.AbsenceType.VACATION,
            start_date=date(2026, 9, 21),
            end_date=date(2026, 9, 22),
            requested_minutes=960,
            calendar_acknowledged=True,
            status=AbsenceRequest.Status.APPROVED,
        )

        summary = vacation_summary(self.account, as_of=date(2026, 9, 8))
        self.assertEqual(summary.vacation_balance_minutes, 3420)
        self.assertEqual(summary.approved_vacation_pending_minutes, 960)
        self.assertEqual(summary.projected_vacation_balance_minutes, 2460)

    def test_nonapproved_requests_do_not_count_as_pending(self):
        AbsenceRequest.objects.create(
            employee=self.employee,
            absence_type=AbsenceRequest.AbsenceType.VACATION,
            start_date=date(2026, 9, 21),
            end_date=date(2026, 9, 21),
            requested_minutes=480,
            calendar_acknowledged=True,
            status=AbsenceRequest.Status.SUBMITTED,
        )

        self.assertEqual(
            approved_vacation_pending_minutes(self.employee, as_of=date(2026, 9, 8)),
            0,
        )
