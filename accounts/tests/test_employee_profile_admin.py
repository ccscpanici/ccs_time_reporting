"""Regression tests for employee birthday and admin supervisor listing."""

from datetime import date

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from accounts.admin import EmployeeProfileAdmin
from accounts.forms import EmployeeProfileForm
from accounts.models import EmployeeProfile


User = get_user_model()


class EmployeeProfileAdminTests(TestCase):
    def setUp(self):
        self.supervisor = User.objects.create_user(
            username="supervisor", first_name="Pat", last_name="Manager"
        )
        self.employee = User.objects.create_user(
            username="employee", first_name="Sam", last_name="Worker"
        )
        self.profile, _ = EmployeeProfile.objects.get_or_create(user=self.employee)
        self.profile.supervisor = self.supervisor
        self.profile.save(update_fields=["supervisor"])
        self.model_admin = EmployeeProfileAdmin(EmployeeProfile, admin.site)

    def test_birthday_is_optional_and_persists(self):
        self.assertIsNone(self.profile.birthday)
        self.profile.birthday = date(1990, 6, 15)
        self.profile.save(update_fields=["birthday"])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.birthday, date(1990, 6, 15))

    def test_admin_shows_employee_and_supervisor(self):
        self.assertEqual(self.model_admin.employee_name(self.profile), "Sam Worker")
        self.assertEqual(self.model_admin.supervisor_name(self.profile), "Pat Manager")
        self.assertIn("birthday", self.model_admin.list_display)
        self.assertIn("supervisor", self.model_admin.list_filter)

    def test_admin_indicates_missing_supervisor(self):
        self.profile.supervisor = None
        self.assertEqual(self.model_admin.supervisor_name(self.profile), "Not assigned")

    def test_supervisor_choices_remain_active_project_managers(self):
        group, _ = Group.objects.get_or_create(name="ProjectManagers")
        self.supervisor.groups.add(group)
        inactive = User.objects.create_user(username="inactive", is_active=False)
        inactive.groups.add(group)
        other = User.objects.create_user(username="other")

        class Request:
            pass

        field = self.model_admin.formfield_for_foreignkey(
            EmployeeProfile._meta.get_field("supervisor"), Request()
        )
        self.assertIn(self.supervisor, field.queryset)
        self.assertNotIn(inactive, field.queryset)
        self.assertNotIn(other, field.queryset)

    def test_employee_facing_profile_form_does_not_expose_birthday_or_supervisor(self):
        form = EmployeeProfileForm(instance=self.profile)
        self.assertNotIn("birthday", form.fields)
        self.assertNotIn("supervisor", form.fields)