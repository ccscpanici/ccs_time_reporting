from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from .base import AppTestCase

from accounts.models import EmployeeProfile
from timesheets.models import Expense, Job, PartEntry, TimeEntry, Timesheet, WorkCode


User = get_user_model()


class TimesheetEditTestBase(AppTestCase):
    week_start = date(2026, 7, 26)
    work_date = date(2026, 7, 27)

    @classmethod
    def setUpTestData(cls):
        cls.employee = User.objects.create_user(
            username="edit_employee",
            password="test-password",
            first_name="Edit",
            last_name="Employee",
            email="edit.employee@gotoccs.com",
        )
        cls.other_employee = User.objects.create_user(
            username="edit_other",
            password="test-password",
            first_name="Other",
            last_name="Employee",
            email="edit.other@gotoccs.com",
        )
        EmployeeProfile.objects.create(user=cls.employee)
        EmployeeProfile.objects.create(user=cls.other_employee)
        cls.work_code, _ = WorkCode.objects.get_or_create(
            code="1800",
            defaults={
                "description": "Employee Development",
            },
        )
        cls.valid_job = Job.objects.create(
            job_number="26001",
            description="Valid test project",
            active=True,
            job_status=Job.STATUS_ACTIVE,
        )
        cls.inactive_job = Job.objects.create(
            job_number="26002",
            description="Inactive test project",
            active=False,
            job_status=Job.STATUS_ACTIVE,
        )

    def make_timesheet(self, *, employee=None, status=Timesheet.Status.DRAFT, entries_per_day=5):
        return self.make_timesheet_record(
            employee=employee or self.employee,
            week_start=self.week_start,
            status=status,
            entries_per_day=entries_per_day,
            mileage_rate=Decimal("0.720"),
        )

    def row_post(self, *, work_date=None, row_order=1, **overrides):
        work_date = work_date or self.work_date
        prefix = f"entry_{work_date.isoformat()}_{row_order}"
        values = {
            f"{prefix}_job_number": "",
            f"{prefix}_work_code": "",
            f"{prefix}_regular_hours": "",
            f"{prefix}_overtime_hours": "",
            f"{prefix}_doubletime_hours": "",
            f"{prefix}_description": "",
            f"{prefix}_expense_miles": "",
            f"{prefix}_expense_per_diem_food": "",
            f"{prefix}_expense_air_fare": "",
            f"{prefix}_expense_hotel": "",
            f"{prefix}_expense_tolls_parking": "",
            f"{prefix}_expense_rental_car_fuel": "",
            f"{prefix}_expense_business_meals": "",
            f"{prefix}_expense_other_expense": "",
            f"{prefix}_expense_explanation_of_expenses": "",
            f"{prefix}_part_ee_stock_job_number": "",
            f"{prefix}_part_quantity": "",
            f"{prefix}_part_description_part_number": "",
            f"{prefix}_part_additional_notes_for_customer": "",
        }
        mapping = {
            "job_number": f"{prefix}_job_number",
            "work_code": f"{prefix}_work_code",
            "regular_hours": f"{prefix}_regular_hours",
            "overtime_hours": f"{prefix}_overtime_hours",
            "doubletime_hours": f"{prefix}_doubletime_hours",
            "description": f"{prefix}_description",
            "miles": f"{prefix}_expense_miles",
            "per_diem_food": f"{prefix}_expense_per_diem_food",
            "air_fare": f"{prefix}_expense_air_fare",
            "hotel": f"{prefix}_expense_hotel",
            "tolls_parking": f"{prefix}_expense_tolls_parking",
            "rental_car_fuel": f"{prefix}_expense_rental_car_fuel",
            "business_meals": f"{prefix}_expense_business_meals",
            "other_expense": f"{prefix}_expense_other_expense",
            "expense_explanation": f"{prefix}_expense_explanation_of_expenses",
            "stock_job_number": f"{prefix}_part_ee_stock_job_number",
            "quantity": f"{prefix}_part_quantity",
            "part_description": f"{prefix}_part_description_part_number",
            "part_notes": f"{prefix}_part_additional_notes_for_customer",
        }
        for key, value in overrides.items():
            if key == "overnight" and value:
                values[f"overnight_{work_date.isoformat()}"] = "on"
            elif key == "reorder_part" and value:
                values[f"{prefix}_part_reorder_part"] = "on"
            else:
                values[mapping[key]] = value
        return values


class TimesheetEditViewTests(TimesheetEditTestBase):
    def test_owner_can_open_draft_timesheet(self):
        timesheet = self.make_timesheet()
        self.client.force_login(self.employee)

        response = self.client.get(reverse("timesheet_edit", args=[timesheet.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["timesheet"], timesheet)

    def test_user_cannot_open_another_employees_timesheet(self):
        timesheet = self.make_timesheet(employee=self.other_employee)
        self.client.force_login(self.employee)

        response = self.client.get(reverse("timesheet_edit", args=[timesheet.pk]))

        self.assertEqual(response.status_code, 404)

    def test_locked_timesheet_redirects_to_detail(self):
        timesheet = self.make_timesheet(status=Timesheet.Status.SUBMITTED)
        self.client.force_login(self.employee)

        response = self.client.get(reverse("timesheet_edit", args=[timesheet.pk]))

        self.assertRedirects(response, reverse("timesheet_detail", args=[timesheet.pk]))

    def test_post_creates_time_entry_and_links_job_and_work_code(self):
        timesheet = self.make_timesheet()
        self.client.force_login(self.employee)
        data = {"entries_per_day": "5"}
        data.update(self.row_post(
            job_number="26001",
            work_code=str(self.work_code.pk),
            regular_hours="8",
            overtime_hours="1.5",
            doubletime_hours="0.5",
            description="Commissioning work",
            overnight=True,
        ))

        response = self.client.post(reverse("timesheet_edit", args=[timesheet.pk]), data)

        entry = TimeEntry.objects.get(timesheet=timesheet, work_date=self.work_date, row_order=1)
        self.assertEqual(entry.job, self.valid_job)
        self.assertEqual(entry.work_code, self.work_code)
        self.assertEqual(entry.regular_hours, Decimal("8"))
        self.assertEqual(entry.overtime_hours, Decimal("1.5"))
        self.assertEqual(entry.doubletime_hours, Decimal("0.5"))
        self.assertTrue(entry.overnight_stay)
        self.assertEqual(entry.description, "Commissioning work")
        self.assertRedirects(response, reverse("timesheet_edit", args=[timesheet.pk]))

    def test_post_updates_existing_time_entry(self):
        timesheet = self.make_timesheet()
        entry = TimeEntry.objects.create(
            timesheet=timesheet,
            work_date=self.work_date,
            row_order=1,
            regular_hours=Decimal("4"),
            description="Old description",
        )
        self.client.force_login(self.employee)
        data = {"entries_per_day": "5"}
        data.update(self.row_post(regular_hours="7.25", description="Updated description"))

        self.client.post(reverse("timesheet_edit", args=[timesheet.pk]), data)

        entry.refresh_from_db()
        self.assertEqual(entry.regular_hours, Decimal("7.25"))
        self.assertEqual(entry.description, "Updated description")
        self.assertEqual(TimeEntry.objects.filter(timesheet=timesheet).count(), 1)

    def test_blank_post_deletes_existing_row_and_related_records(self):
        timesheet = self.make_timesheet()
        entry = TimeEntry.objects.create(
            timesheet=timesheet,
            work_date=self.work_date,
            row_order=1,
            regular_hours=Decimal("4"),
        )
        Expense.objects.create(time_entry=entry, miles=Decimal("10"))
        PartEntry.objects.create(time_entry=entry, quantity=1, part_description_part_number="Fuse")
        self.client.force_login(self.employee)
        data = {"entries_per_day": "5"}
        data.update(self.row_post())

        self.client.post(reverse("timesheet_edit", args=[timesheet.pk]), data)

        self.assertFalse(TimeEntry.objects.filter(pk=entry.pk).exists())
        self.assertFalse(Expense.objects.filter(time_entry_id=entry.pk).exists())
        self.assertFalse(PartEntry.objects.filter(time_entry_id=entry.pk).exists())

    def test_post_creates_expense_and_calculates_mileage(self):
        timesheet = self.make_timesheet()
        self.client.force_login(self.employee)
        data = {"entries_per_day": "5"}
        data.update(self.row_post(
            regular_hours="1",
            miles="100",
            hotel="125.50",
            other_expense="10",
            expense_explanation="Customer-site travel",
        ))

        self.client.post(reverse("timesheet_edit", args=[timesheet.pk]), data)

        expense = Expense.objects.get(time_entry__timesheet=timesheet)
        self.assertEqual(expense.miles, Decimal("100"))
        self.assertEqual(expense.mileage.amount, Decimal("72.00"))
        self.assertEqual(expense.hotel.amount, Decimal("125.50"))
        self.assertEqual(expense.other_expense.amount, Decimal("10.00"))
        self.assertEqual(expense.explanation_of_expenses, "Customer-site travel")

    def test_post_creates_part_entry(self):
        timesheet = self.make_timesheet()
        self.client.force_login(self.employee)
        data = {"entries_per_day": "5"}
        data.update(self.row_post(
            regular_hours="1",
            stock_job_number="STOCK",
            quantity="3",
            part_description="1769-IF8 analog input",
            part_notes="Ship to customer",
            reorder_part=True,
        ))

        self.client.post(reverse("timesheet_edit", args=[timesheet.pk]), data)

        part = PartEntry.objects.get(time_entry__timesheet=timesheet)
        self.assertEqual(part.ee_stock_job_number, "STOCK")
        self.assertEqual(part.quantity, Decimal("3"))
        self.assertEqual(part.part_description_part_number, "1769-IF8 analog input")
        self.assertEqual(part.additional_notes_for_customer, "Ship to customer")
        self.assertTrue(part.reorder_part)

    def test_invalid_job_number_prevents_save(self):
        timesheet = self.make_timesheet()
        self.client.force_login(self.employee)
        data = {"entries_per_day": "5"}
        data.update(self.row_post(job_number="DOES-NOT-EXIST", regular_hours="8"))

        response = self.client.post(reverse("timesheet_edit", args=[timesheet.pk]), data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "is not available for time entry")
        self.assertFalse(TimeEntry.objects.filter(timesheet=timesheet).exists())

    def test_inactive_job_number_prevents_save(self):
        timesheet = self.make_timesheet()
        self.client.force_login(self.employee)
        data = {"entries_per_day": "5"}
        data.update(self.row_post(job_number=self.inactive_job.job_number, regular_hours="8"))

        response = self.client.post(reverse("timesheet_edit", args=[timesheet.pk]), data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "is not available for time entry")
        self.assertFalse(TimeEntry.objects.filter(timesheet=timesheet).exists())

    def test_entries_per_day_is_clamped_to_supported_range(self):
        timesheet = self.make_timesheet()
        self.client.force_login(self.employee)

        self.client.post(reverse("timesheet_edit", args=[timesheet.pk]), {"entries_per_day": "99"})

        timesheet.refresh_from_db()
        self.assertEqual(timesheet.entries_per_day, 25)


class TimesheetAutosaveTests(TimesheetEditTestBase):
    def test_autosave_requires_post(self):
        self.client.force_login(self.employee)

        response = self.client.get(reverse("timesheet_autosave"))

        self.assertEqual(response.status_code, 405)

    def test_autosave_rejects_invalid_work_date(self):
        self.client.force_login(self.employee)

        response = self.client.post(reverse("timesheet_autosave"), {"work_date": "not-a-date"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"ok": False, "error": "Invalid work date."})

    def test_autosave_creates_timesheet_and_entry(self):
        self.client.force_login(self.employee)
        data = {"work_date": self.work_date.isoformat(), "entries_per_day": "5"}
        data.update(self.row_post(regular_hours="8", description="Autosaved work"))

        response = self.client.post(reverse("timesheet_autosave"), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        timesheet = Timesheet.objects.get(employee=self.employee, week_start=self.week_start)
        entry = TimeEntry.objects.get(timesheet=timesheet, work_date=self.work_date, row_order=1)
        self.assertEqual(entry.regular_hours, Decimal("8"))
        self.assertEqual(entry.description, "Autosaved work")


    def test_autosave_accepts_fractional_hour_value(self):
        self.client.force_login(self.employee)
        data = {"work_date": self.work_date.isoformat(), "entries_per_day": "5"}
        data.update(self.row_post(regular_hours="0.1"))

        response = self.client.post(reverse("timesheet_autosave"), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

        timesheet = Timesheet.objects.get(employee=self.employee, week_start=self.week_start)
        entry = TimeEntry.objects.get(timesheet=timesheet, work_date=self.work_date, row_order=1)
        self.assertEqual(entry.regular_hours, Decimal("0.1"))

    def test_autosave_accepts_24_hours(self):
        self.client.force_login(self.employee)
        data = {"work_date": self.work_date.isoformat(), "entries_per_day": "5"}
        data.update(self.row_post(regular_hours="24"))

        response = self.client.post(reverse("timesheet_autosave"), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

        timesheet = Timesheet.objects.get(employee=self.employee, week_start=self.week_start)
        entry = TimeEntry.objects.get(timesheet=timesheet, work_date=self.work_date, row_order=1)
        self.assertEqual(entry.regular_hours, Decimal("24"))

    def test_autosave_rejects_hours_above_24(self):
        self.client.force_login(self.employee)
        data = {"work_date": self.work_date.isoformat(), "entries_per_day": "5"}
        data.update(self.row_post(regular_hours="24.1"))

        response = self.client.post(reverse("timesheet_autosave"), data)

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertIn("Regular hours must be between 0 and 24.", payload["errors"][0])

        timesheet = Timesheet.objects.get(employee=self.employee, week_start=self.week_start)
        self.assertFalse(TimeEntry.objects.filter(timesheet=timesheet).exists())

    def test_autosave_rejects_negative_hours(self):
        self.client.force_login(self.employee)
        data = {"work_date": self.work_date.isoformat(), "entries_per_day": "5"}
        data.update(self.row_post(regular_hours="-0.1"))

        response = self.client.post(reverse("timesheet_autosave"), data)

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertIn("Regular hours must be between 0 and 24.", payload["errors"][0])

        timesheet = Timesheet.objects.get(employee=self.employee, week_start=self.week_start)
        self.assertFalse(TimeEntry.objects.filter(timesheet=timesheet).exists())

    def test_weekly_autosave_updates_non_today_entry(self):
        timesheet = self.make_timesheet()
        self.client.force_login(self.employee)

        non_today = self.week_start + timedelta(days=4)

        TimeEntry.objects.create(
            timesheet=timesheet,
            work_date=non_today,
            row_order=1,
            regular_hours=Decimal("5.50"),
        )

        data = {
            "timesheet_id": str(timesheet.pk),
            "entries_per_day": "5",
            f"entry_{non_today.isoformat()}_1_regular_hours": "6.25",
        }

        response = self.client.post(reverse("timesheet_autosave"), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

        entry = TimeEntry.objects.get(
            timesheet=timesheet,
            work_date=non_today,
            row_order=1,
        )
        self.assertEqual(entry.regular_hours, Decimal("6.25"))

    def test_autosave_returns_validation_errors_for_invalid_job(self):
        self.make_timesheet()
        self.client.force_login(self.employee)
        data = {"work_date": self.work_date.isoformat(), "entries_per_day": "5"}
        data.update(self.row_post(job_number="BAD-JOB", regular_hours="8"))

        response = self.client.post(reverse("timesheet_autosave"), data)

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertIn("BAD-JOB", payload["errors"][0])

    def test_autosave_rejects_locked_timesheet(self):
        self.make_timesheet(status=Timesheet.Status.APPROVED)
        self.client.force_login(self.employee)

        response = self.client.post(
            reverse("timesheet_autosave"),
            {"work_date": self.work_date.isoformat(), "entries_per_day": "5"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"ok": False, "error": "Timesheet is locked."})

    def test_autosave_only_modifies_logged_in_users_timesheet(self):
        other_timesheet = self.make_timesheet(employee=self.other_employee)
        self.client.force_login(self.employee)
        data = {"work_date": self.work_date.isoformat(), "entries_per_day": "5"}
        data.update(self.row_post(regular_hours="2"))

        response = self.client.post(reverse("timesheet_autosave"), data)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TimeEntry.objects.filter(timesheet=other_timesheet).exists())
        own_timesheet = Timesheet.objects.get(employee=self.employee, week_start=self.week_start)
        self.assertTrue(TimeEntry.objects.filter(timesheet=own_timesheet).exists())