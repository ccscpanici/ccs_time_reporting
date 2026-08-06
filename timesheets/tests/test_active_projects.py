from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from timesheets.models import ActiveProject, Job, TimeEntry, Timesheet


User = get_user_model()


class ActiveProjectTestBase(TestCase):
    week_start = date(2026, 8, 2)

    @classmethod
    def setUpTestData(cls):
        cls.employee = User.objects.create_user(
            username="employee",
            password="test-password",
            first_name="Regular",
            last_name="Employee",
            email="employee@gotoccs.com",
        )
        cls.manager = User.objects.create_user(
            username="manager",
            password="test-password",
            first_name="Project",
            last_name="Manager",
            email="manager@gotoccs.com",
        )
        cls.other_manager = User.objects.create_user(
            username="othermanager",
            password="test-password",
            first_name="Other",
            last_name="Manager",
            email="othermanager@gotoccs.com",
        )

        manager_group, _ = Group.objects.get_or_create(name="ProjectManagers")
        cls.manager.groups.add(manager_group)
        cls.other_manager.groups.add(manager_group)

        cls.job_26001 = Job.objects.create(
            job_number="26001",
            description="Primary active job",
            job_status=Job.STATUS_ACTIVE,
            active=True,
        )
        cls.job_26002 = Job.objects.create(
            job_number="26002",
            description="Second active job",
            job_status=Job.STATUS_ACTIVE,
            active=True,
        )
        cls.inactive_job = Job.objects.create(
            job_number="25001",
            description="Inactive job",
            job_status=Job.STATUS_COMPLETE,
            active=False,
        )
        cls.blank_description_job = Job.objects.create(
            job_number="26003",
            description="",
            job_status=Job.STATUS_ACTIVE,
            active=True,
        )

    def make_project(
        self,
        *,
        job_number="26001",
        budgeted_hours=Decimal("100.00"),
        active=True,
        created_by=None,
        updated_by=None,
    ):
        return ActiveProject.objects.create(
            job_number=job_number,
            budgeted_hours=budgeted_hours,
            active=active,
            created_by=created_by or self.manager,
            updated_by=updated_by or self.manager,
        )

    def make_entry(
        self,
        *,
        employee=None,
        job_number="26001",
        linked_job=None,
        regular=Decimal("0.00"),
        overtime=Decimal("0.00"),
        doubletime=Decimal("0.00"),
        status=Timesheet.Status.APPROVED,
        deleted=False,
        row_order=1,
    ):
        employee = employee or self.employee

        existing_weeks = set(
            Timesheet.objects.filter(employee=employee).values_list(
                "week_start",
                flat=True,
            )
        )
        week_start = self.week_start
        while week_start in existing_weeks:
            week_start += timezone.timedelta(days=7)

        timesheet = Timesheet.objects.create(
            employee=employee,
            week_start=week_start,
            status=status,
            deleted_at=timezone.now() if deleted else None,
        )
        return TimeEntry.objects.create(
            timesheet=timesheet,
            work_date=week_start,
            row_order=row_order,
            job_number=job_number,
            job=linked_job,
            regular_hours=regular,
            overtime_hours=overtime,
            doubletime_hours=doubletime,
            description="Active project test work",
        )


class ActiveProjectPermissionTests(ActiveProjectTestBase):
    def test_anonymous_user_is_redirected_to_login(self):
        url = reverse("active_project_list")

        response = self.client.get(url)

        self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_regular_employee_is_redirected_from_all_active_project_views(self):
        project = self.make_project()
        self.client.force_login(self.employee)
        urls = [
            reverse("active_project_list"),
            reverse("active_project_detail", args=[project.pk]),
            reverse("active_project_create"),
            reverse("active_project_edit", args=[project.pk]),
            reverse("active_project_remove", args=[project.pk]),
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, reverse("timesheet_list"))

    def test_project_manager_can_open_all_read_and_form_pages(self):
        project = self.make_project()
        self.client.force_login(self.manager)
        urls = [
            reverse("active_project_list"),
            reverse("active_project_detail", args=[project.pk]),
            reverse("active_project_create"),
            reverse("active_project_edit", args=[project.pk]),
        ]

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)


class ActiveProjectListTests(ActiveProjectTestBase):
    def test_list_only_shows_active_projects_in_job_number_order(self):
        second = self.make_project(job_number="26002")
        first = self.make_project(job_number="26001")
        self.make_project(job_number="25001", active=False)
        self.client.force_login(self.manager)

        response = self.client.get(reverse("active_project_list"))

        self.assertEqual(response.status_code, 200)
        projects = [row["project"] for row in response.context["rows"]]
        self.assertEqual(projects, [first, second])

    def test_list_calculates_billed_remaining_and_percent_used(self):
        project = self.make_project(budgeted_hours=Decimal("40.00"))
        self.make_entry(
            regular=Decimal("8.00"),
            overtime=Decimal("2.00"),
            doubletime=Decimal("1.00"),
        )
        self.make_entry(
            employee=self.other_manager,
            job_number="26001",
            regular=Decimal("5.00"),
            row_order=2,
        )
        self.client.force_login(self.manager)

        response = self.client.get(reverse("active_project_list"))

        row = response.context["rows"][0]
        self.assertEqual(row["project"], project)
        self.assertEqual(row["billed_hours"], Decimal("16.00"))
        self.assertEqual(row["remaining_hours"], Decimal("24.00"))
        self.assertEqual(row["percent_used"], Decimal("40.00"))

    def test_list_excludes_voided_and_deleted_timesheet_hours(self):
        self.make_project(budgeted_hours=Decimal("20.00"))
        self.make_entry(regular=Decimal("5.00"))
        self.make_entry(regular=Decimal("7.00"), status=Timesheet.Status.VOID, row_order=2)
        self.make_entry(regular=Decimal("9.00"), deleted=True, row_order=3)
        self.client.force_login(self.manager)

        response = self.client.get(reverse("active_project_list"))

        row = response.context["rows"][0]
        self.assertEqual(row["billed_hours"], Decimal("5.00"))
        self.assertEqual(row["remaining_hours"], Decimal("15.00"))

    def test_zero_budget_project_has_zero_percent_used(self):
        self.make_project(budgeted_hours=Decimal("0.00"))
        self.make_entry(regular=Decimal("4.00"))
        self.client.force_login(self.manager)

        response = self.client.get(reverse("active_project_list"))

        row = response.context["rows"][0]
        self.assertEqual(row["percent_used"], 0)
        self.assertEqual(row["remaining_hours"], Decimal("-4.00"))


class ActiveProjectDetailTests(ActiveProjectTestBase):
    def test_detail_calculates_hour_totals_and_budget_statistics(self):
        project = self.make_project(budgeted_hours=Decimal("50.00"))
        self.make_entry(
            regular=Decimal("8.00"),
            overtime=Decimal("2.00"),
            doubletime=Decimal("1.00"),
        )
        self.make_entry(
            employee=self.other_manager,
            regular=Decimal("5.00"),
            overtime=Decimal("1.00"),
            row_order=2,
        )
        self.client.force_login(self.manager)

        response = self.client.get(reverse("active_project_detail", args=[project.pk]))

        self.assertEqual(response.context["total_regular"], Decimal("13.00"))
        self.assertEqual(response.context["total_overtime"], Decimal("3.00"))
        self.assertEqual(response.context["total_doubletime"], Decimal("1.00"))
        self.assertEqual(response.context["total_billed"], Decimal("17.00"))
        self.assertEqual(response.context["remaining_hours"], Decimal("33.00"))
        self.assertEqual(response.context["percent_used"], Decimal("34.00"))

    def test_detail_aggregates_and_sorts_employee_rows_by_total_hours(self):
        project = self.make_project()
        self.make_entry(
            employee=self.employee,
            regular=Decimal("4.00"),
            overtime=Decimal("1.00"),
        )
        self.make_entry(
            employee=self.other_manager,
            regular=Decimal("8.00"),
            doubletime=Decimal("2.00"),
            row_order=2,
        )
        self.client.force_login(self.manager)

        response = self.client.get(reverse("active_project_detail", args=[project.pk]))

        employee_rows = response.context["employee_rows"]
        self.assertEqual([row["employee_name"] for row in employee_rows], ["Other Manager", "Regular Employee"])
        self.assertEqual(employee_rows[0]["total_hours"], Decimal("10.00"))
        self.assertEqual(employee_rows[1]["total_hours"], Decimal("5.00"))

    def test_detail_matches_direct_and_linked_job_numbers_case_insensitively(self):
        project = self.make_project(job_number="26001")
        self.make_entry(job_number="26001", regular=Decimal("3.00"))
        self.make_entry(
            job_number="",
            linked_job=self.job_26001,
            regular=Decimal("4.00"),
            row_order=2,
        )
        TimeEntry.objects.filter(row_order=1).update(job_number="26001")
        ActiveProject.objects.filter(pk=project.pk).update(job_number="26001")
        self.client.force_login(self.manager)

        response = self.client.get(reverse("active_project_detail", args=[project.pk]))

        self.assertEqual(response.context["total_billed"], Decimal("7.00"))
        self.assertEqual(len(response.context["detail_rows"]), 2)

    def test_detail_excludes_voided_deleted_and_other_job_entries(self):
        project = self.make_project()
        self.make_entry(regular=Decimal("5.00"))
        self.make_entry(regular=Decimal("7.00"), status=Timesheet.Status.VOID, row_order=2)
        self.make_entry(regular=Decimal("9.00"), deleted=True, row_order=3)
        self.make_entry(job_number="26002", regular=Decimal("11.00"), row_order=4)
        self.client.force_login(self.manager)

        response = self.client.get(reverse("active_project_detail", args=[project.pk]))

        self.assertEqual(response.context["total_billed"], Decimal("5.00"))
        self.assertEqual(len(response.context["detail_rows"]), 1)

    def test_missing_project_returns_404_for_project_manager(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("active_project_detail", args=[999999]))

        self.assertEqual(response.status_code, 404)


class ActiveProjectCreateTests(ActiveProjectTestBase):
    def test_create_get_uses_active_initial_and_valid_job_options(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("active_project_create"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].initial["active"])
        job_numbers = [option["job_number"] for option in response.context["job_options"]]
        self.assertIn("26001", job_numbers)
        self.assertIn("26002", job_numbers)
        self.assertNotIn("25001", job_numbers)
        self.assertNotIn("26003", job_numbers)

    def test_valid_post_creates_project_and_sets_audit_fields(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("active_project_create"),
            {
                "job_number": "26001",
                "budgeted_hours": "125.50",
                "active": "on",
            },
        )

        project = ActiveProject.objects.get(job_number="26001")
        self.assertEqual(project.budgeted_hours, Decimal("125.50"))
        self.assertTrue(project.active)
        self.assertEqual(project.created_by, self.manager)
        self.assertEqual(project.updated_by, self.manager)
        self.assertRedirects(response, reverse("active_project_list"))

    def test_create_normalizes_job_number_to_stored_case(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("active_project_create"),
            {"job_number": "26001", "budgeted_hours": "10.00", "active": "on"},
        )

        self.assertRedirects(response, reverse("active_project_list"))
        self.assertTrue(ActiveProject.objects.filter(job_number=self.job_26001.job_number).exists())

    def test_invalid_inactive_or_blank_description_job_is_rejected(self):
        self.client.force_login(self.manager)

        for job_number in ["DOES-NOT-EXIST", "25001", "26003"]:
            with self.subTest(job_number=job_number):
                response = self.client.post(
                    reverse("active_project_create"),
                    {"job_number": job_number, "budgeted_hours": "10.00", "active": "on"},
                )
                self.assertEqual(response.status_code, 200)
                self.assertFormError(response.context["form"], "job_number", "Select a valid active job from the job list.")

        self.assertEqual(ActiveProject.objects.count(), 0)

    def test_duplicate_active_project_is_rejected(self):
        self.make_project(job_number="26001")
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("active_project_create"),
            {"job_number": "26001", "budgeted_hours": "25.00", "active": "on"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "job_number", "This job is already on the Active Projects list.")
        self.assertEqual(ActiveProject.objects.filter(job_number="26001").count(), 1)


class ActiveProjectEditAndRemoveTests(ActiveProjectTestBase):
    def test_edit_get_loads_existing_project(self):
        project = self.make_project(budgeted_hours=Decimal("80.00"))
        self.client.force_login(self.manager)

        response = self.client.get(reverse("active_project_edit", args=[project.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["project"], project)
        self.assertEqual(response.context["form"].instance, project)

    def test_valid_edit_updates_fields_and_updated_by_only(self):
        project = self.make_project(created_by=self.manager, updated_by=self.manager)
        self.client.force_login(self.other_manager)

        response = self.client.post(
            reverse("active_project_edit", args=[project.pk]),
            {
                "job_number": "26001",
                "budgeted_hours": "175.25",
                "active": "on",
            },
        )

        project.refresh_from_db()
        self.assertEqual(project.budgeted_hours, Decimal("175.25"))
        self.assertEqual(project.created_by, self.manager)
        self.assertEqual(project.updated_by, self.other_manager)
        self.assertRedirects(response, reverse("active_project_list"))

    def test_edit_can_change_project_to_another_valid_unused_job(self):
        project = self.make_project(job_number="26001")
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("active_project_edit", args=[project.pk]),
            {"job_number": "26002", "budgeted_hours": "50.00", "active": "on"},
        )

        project.refresh_from_db()
        self.assertEqual(project.job_number, "26002")
        self.assertRedirects(response, reverse("active_project_list"))

    def test_edit_rejects_job_already_used_by_another_active_project(self):
        project = self.make_project(job_number="26001")
        self.make_project(job_number="26002")
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("active_project_edit", args=[project.pk]),
            {"job_number": "26002", "budgeted_hours": "50.00", "active": "on"},
        )

        project.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "job_number", "This job is already on the Active Projects list.")
        self.assertEqual(project.job_number, "26001")

    def test_remove_get_does_not_delete_project(self):
        project = self.make_project()
        self.client.force_login(self.manager)

        response = self.client.get(reverse("active_project_remove", args=[project.pk]))

        self.assertTrue(ActiveProject.objects.filter(pk=project.pk).exists())
        self.assertRedirects(response, reverse("active_project_list"))

    def test_remove_post_deletes_project(self):
        project = self.make_project()
        self.client.force_login(self.manager)

        response = self.client.post(reverse("active_project_remove", args=[project.pk]))

        self.assertFalse(ActiveProject.objects.filter(pk=project.pk).exists())
        self.assertRedirects(response, reverse("active_project_list"))

    def test_remove_missing_project_returns_404(self):
        self.client.force_login(self.manager)

        response = self.client.post(reverse("active_project_remove", args=[999999]))

        self.assertEqual(response.status_code, 404)