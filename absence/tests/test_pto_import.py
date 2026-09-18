from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import EmployeeProfile

from absence.models import PTOAccount, PTOAccountChange, PTOImport, PTOImportRow
from absence.services.pto_import import apply_pto_import, match_employee, parse_pto_text, parse_report_date

User = get_user_model()


SAMPLE_TEXT = """
Employee Sick Available Sick Used Vacation Available Vacation Used
Beyer, Joshua A -22:00 14:00 -26:16 100:00
Panici, Christopher J -109:00 17:30 73:01 63:00
11:25 AM Complete Control Solutions, Inc.
09/08/26 Paid Time Off List
September 8, 2026
"""


class PTOImportParsingTests(TestCase):
    def test_parses_report_rows_and_date(self):
        rows = parse_pto_text(SAMPLE_TEXT)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].employee_name, "Beyer, Joshua A")
        self.assertEqual(rows[0].vacation_available_minutes, -(26 * 60 + 16))
        self.assertEqual(rows[1].sick_used_minutes, 17 * 60 + 30)
        self.assertEqual(parse_report_date(SAMPLE_TEXT), date(2026, 9, 8))

    def test_matches_report_last_first_name_to_active_user(self):
        user = User.objects.create_user(username="jbeyer", first_name="Joshua", last_name="Beyer")
        EmployeeProfile.objects.create(user=user)
        matched, status, message = match_employee("Beyer, Joshua A")
        self.assertEqual(matched, user)
        self.assertEqual(status, PTOImportRow.MatchStatus.MATCHED)
        self.assertEqual(message, "")


class PTOImportApplyTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="manager", first_name="Manager", last_name="User")
        self.employee = User.objects.create_user(username="employee", first_name="Joshua", last_name="Beyer")
        self.pto_import = PTOImport.objects.create(
            source_file="absence/pto_imports/test.pdf",
            source_name="PTOList.pdf",
            report_date=date(2026, 9, 8),
            uploaded_by=self.manager,
        )
        PTOImportRow.objects.create(
            pto_import=self.pto_import,
            row_number=1,
            employee_name="Beyer, Joshua A",
            employee=self.employee,
            match_status=PTOImportRow.MatchStatus.MATCHED,
            sick_available_minutes=-1320,
            sick_used_minutes=840,
            vacation_available_minutes=-1576,
            vacation_used_minutes=6000,
        )

    def test_apply_updates_account_but_preserves_manual_entitlement(self):
        PTOAccount.objects.create(employee=self.employee, vacation_weeks_per_year=3, vacation_balance_minutes=0)

        apply_pto_import(self.pto_import, self.manager)

        account = PTOAccount.objects.get(employee=self.employee)
        self.assertEqual(account.vacation_weeks_per_year, 3)
        self.assertEqual(account.vacation_balance_minutes, -1576)
        self.assertEqual(account.sick_balance_minutes, -1320)
        self.assertEqual(account.balance_as_of, date(2026, 9, 8))
        self.assertEqual(PTOAccountChange.objects.filter(pto_account=account, source=PTOAccountChange.Source.IMPORT).count(), 1)
        self.pto_import.refresh_from_db()
        self.assertEqual(self.pto_import.status, PTOImport.Status.APPLIED)

    def test_apply_skips_unmatched_rows(self):
        PTOImportRow.objects.create(
            pto_import=self.pto_import,
            row_number=2,
            employee_name="Employee, Other",
            employee=None,
            match_status=PTOImportRow.MatchStatus.UNMATCHED,
            sick_available_minutes=-60,
            sick_used_minutes=120,
            vacation_available_minutes=480,
            vacation_used_minutes=240,
        )

        apply_pto_import(self.pto_import, self.manager)

        self.assertEqual(PTOAccount.objects.count(), 1)
        account = PTOAccount.objects.get(employee=self.employee)
        self.assertEqual(account.vacation_accrual_minutes, -1576)

    def test_apply_refuses_import_with_no_matched_rows(self):
        row = self.pto_import.rows.get()
        row.match_status = PTOImportRow.MatchStatus.UNMATCHED
        row.employee = None
        row.save()

        with self.assertRaisesMessage(
            ValueError,
            "This import does not contain any matched employees to apply.",
        ):
            apply_pto_import(self.pto_import, self.manager)

    def test_apply_refuses_duplicate_matched_employee_rows(self):
        PTOImportRow.objects.create(
            pto_import=self.pto_import,
            row_number=2,
            employee_name="Beyer, Joshua duplicate",
            employee=self.employee,
            match_status=PTOImportRow.MatchStatus.MATCHED,
            sick_available_minutes=-1320,
            sick_used_minutes=840,
            vacation_available_minutes=-1576,
            vacation_used_minutes=6000,
        )

        with self.assertRaisesMessage(ValueError, "Two or more matched report rows"):
            apply_pto_import(self.pto_import, self.manager)
