"""Shared base classes and helpers for application tests."""
from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from . import factories


class AppTestCase(TestCase):
    """Common helpers without imposing fixture data on subclasses."""

    default_password = "test-password"

    @classmethod
    def make_user(cls, **kwargs):
        """Provide the make user helper used by this test suite."""
        kwargs.setdefault("password", cls.default_password)
        return factories.make_user(**kwargs)

    @classmethod
    def add_to_group(cls, user, name):
        """Provide the add to group helper used by this test suite."""
        return factories.add_user_to_group(user, name)

    @classmethod
    def make_profile(cls, **kwargs):
        """Provide the make profile helper used by this test suite."""
        return factories.make_employee_profile(**kwargs)

    def login(self, user):
        """Provide the login helper used by this test suite."""
        self.client.force_login(user)
        return user

    def assert_login_required(self, url, *, method="get", data=None):
        """Provide the assert login required helper used by this test suite."""
        response = getattr(self.client, method)(url, data or {})
        self.assertRedirects(response, f"{reverse('login')}?next={url}")
        return response

    def make_customer(self, **kwargs):
        """Provide the make customer helper used by this test suite."""
        return factories.make_customer(**kwargs)

    def make_job_record(self, **kwargs):
        """Provide the make job record helper used by this test suite."""
        return factories.make_job(**kwargs)

    def make_timesheet_record(self, **kwargs):
        """Provide the make timesheet record helper used by this test suite."""
        return factories.make_timesheet(**kwargs)

    def make_time_entry_record(self, **kwargs):
        """Provide the make time entry record helper used by this test suite."""
        return factories.make_time_entry(**kwargs)
