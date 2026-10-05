"""Reusable assertion mixins for view and workflow tests."""
from django.urls import reverse


class AuthenticationAssertionsMixin:
    """Exercise the authentication assertions mixin workflow and protect its expected behavior from regressions."""
    def assert_redirected_to_login(self, response, url):
        """Provide the assert redirected to login helper used by this test suite."""
        self.assertRedirects(response, f"{reverse('login')}?next={url}")


class ResponseAssertionsMixin:
    """Exercise the response assertions mixin workflow and protect its expected behavior from regressions."""
    def assert_ok(self, response):
        """Provide the assert ok helper used by this test suite."""
        self.assertEqual(response.status_code, 200)

    def assert_not_found(self, response):
        """Provide the assert not found helper used by this test suite."""
        self.assertEqual(response.status_code, 404)
