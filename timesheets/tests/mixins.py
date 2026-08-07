"""Reusable assertion mixins for view and workflow tests."""
from django.urls import reverse


class AuthenticationAssertionsMixin:
    def assert_redirected_to_login(self, response, url):
        self.assertRedirects(response, f"{reverse('login')}?next={url}")


class ResponseAssertionsMixin:
    def assert_ok(self, response):
        self.assertEqual(response.status_code, 200)

    def assert_not_found(self, response):
        self.assertEqual(response.status_code, 404)
