from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.urls import reverse

from accounts.models import EmployeeProfile, OfficeLocation, UserPreference
from timesheets.tests.base import AppTestCase

User = get_user_model()


class AccountsViewTestCase(AppTestCase):
    def make_office(self, name="Appleton", *, active=True, **overrides):
        values = {
            "address_1": "123 Main Street",
            "address_2": "",
            "city": "Appleton",
            "state": "WI",
            "postal_code": "54911",
            "active": active,
        }
        values.update(overrides)
        return OfficeLocation.objects.create(name=name, **values)

    def messages_for(self, response):
        return [str(message) for message in get_messages(response.wsgi_request)]


class SignupViewTests(AccountsViewTestCase):
    def signup_data(self, **overrides):
        values = {
            "username": "newemployee",
            "first_name": "New",
            "last_name": "Employee",
            "email": "New.Employee@GoToCCS.com",
            "password1": "Safe-test-password-123!",
            "password2": "Safe-test-password-123!",
        }
        values.update(overrides)
        return values

    def test_signup_get_renders_empty_form(self):
        response = self.client.get(reverse("signup"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/signup.html")
        self.assertIn("form", response.context)
        self.assertFalse(response.context["form"].is_bound)

    def test_authenticated_user_is_redirected_to_timesheet_list(self):
        user = self.make_user(username="existing")
        self.login(user)

        response = self.client.get(reverse("signup"))

        self.assertRedirects(response, reverse("timesheet_list"))

    def test_valid_signup_creates_user_profile_logs_in_and_uses_first_active_office(self):
        self.make_office("Zeta Office")
        expected_office = OfficeLocation.objects.get(name="Appleton Office")
        self.make_office("Aardvark Closed", active=False)

        response = self.client.post(reverse("signup"), self.signup_data(), follow=True)

        user = User.objects.get(username="newemployee")
        profile = EmployeeProfile.objects.get(user=user)
        self.assertEqual(user.first_name, "New")
        self.assertEqual(user.last_name, "Employee")
        self.assertEqual(user.email, "new.employee@gotoccs.com")
        self.assertEqual(profile.office_location, expected_office)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertRedirects(response, reverse("profile"))
        self.assertIn("Account created. Please complete your profile.", self.messages_for(response))

    def test_valid_signup_allows_profile_without_office_when_none_exist(self):
        OfficeLocation.objects.all().delete()

        response = self.client.post(
            reverse("signup"),
            self.signup_data(),
        )

        user = User.objects.get(username="newemployee")

        self.assertRedirects(response, reverse("profile"))
        self.assertIsNone(user.employee_profile.office_location)
        
    def test_non_company_email_is_rejected_without_creating_user(self):
        response = self.client.post(
            reverse("signup"),
            self.signup_data(email="employee@example.com"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="newemployee").exists())
        self.assertFormError(
            response.context["form"],
            "email",
            "You must use a @gotoccs.com email address to sign up.",
        )

    def test_duplicate_email_is_rejected_case_insensitively(self):
        self.make_user(username="existing", email="new.employee@gotoccs.com")

        response = self.client.post(reverse("signup"), self.signup_data())

        self.assertFalse(User.objects.filter(username="newemployee").exists())
        self.assertFormError(
            response.context["form"],
            "email",
            "A user with this email address already exists.",
        )

    def test_invalid_password_confirmation_redisplays_bound_form(self):
        response = self.client.post(
            reverse("signup"),
            self.signup_data(password2="different-password"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].is_bound)
        self.assertFalse(User.objects.filter(username="newemployee").exists())
        self.assertIn("password2", response.context["form"].errors)


class ProfileViewTests(AccountsViewTestCase):
    def profile_data(self, office, **overrides):
        values = {
            "first_name": "Updated",
            "last_name": "Person",
            "email": "updated@gotoccs.com",
            "office_location": str(office.pk),
            "address_1": "456 Home Road",
            "address_2": "Unit 2",
            "city": "Mosinee",
            "state": "WI",
            "postal_code": "54455",
        }
        values.update(overrides)
        return values

    def test_profile_requires_login(self):
        self.assert_login_required(reverse("profile"))

    def test_profile_get_creates_profile_with_first_active_office(self):
        self.make_office("Zeta Office")
        expected_office = OfficeLocation.objects.get(name="Appleton Office")
        user = self.make_user(username="profileuser")
        self.login(user)

        response = self.client.get(reverse("profile"))

        profile = EmployeeProfile.objects.get(user=user)
        self.assertEqual(profile.office_location, expected_office)
        self.assertEqual(response.context["employee_profile"], profile)
        self.assertEqual(response.context["user_form"].instance, user)
        self.assertEqual(response.context["employee_form"].instance, profile)
        self.assertTemplateUsed(response, "accounts/profile.html")

    def test_profile_get_preserves_existing_profile_office(self):
        first_office = self.make_office("Appleton")
        existing_office = self.make_office("Mosinee")
        user = self.make_user(username="profileuser")
        profile = self.make_profile(user=user, office_location=existing_office)
        self.login(user)

        response = self.client.get(reverse("profile"))

        profile.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(profile.office_location, first_office)
        self.assertEqual(profile.office_location, existing_office)

    def test_valid_profile_post_updates_user_and_address(self):
        old_office = self.make_office("Appleton")
        new_office = self.make_office("Mosinee")
        user = self.make_user(username="profileuser", first_name="Old", last_name="Name")
        profile = self.make_profile(user=user, office_location=old_office)
        self.login(user)

        response = self.client.post(
            reverse("profile"),
            self.profile_data(new_office),
            follow=True,
        )

        user.refresh_from_db()
        profile.refresh_from_db()
        self.assertRedirects(response, reverse("profile"))
        self.assertEqual((user.first_name, user.last_name, user.email), ("Updated", "Person", "updated@gotoccs.com"))
        self.assertEqual(profile.office_location, new_office)
        self.assertEqual(profile.address_1, "456 Home Road")
        self.assertEqual(profile.address_2, "Unit 2")
        self.assertEqual(profile.city, "Mosinee")
        self.assertEqual(profile.state, "WI")
        self.assertEqual(profile.postal_code, "54455")
        self.assertIn("Profile updated.", self.messages_for(response))

    def test_invalid_employee_form_does_not_save_either_form(self):
        active_office = self.make_office("Appleton")
        inactive_office = self.make_office("Closed", active=False)
        user = self.make_user(
            username="profileuser",
            first_name="Original",
            last_name="User",
            email="original@gotoccs.com",
        )
        profile = self.make_profile(user=user, office_location=active_office, city="Appleton")
        self.login(user)

        response = self.client.post(
            reverse("profile"),
            self.profile_data(inactive_office),
        )

        user.refresh_from_db()
        profile.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(user.first_name, "Original")
        self.assertEqual(user.email, "original@gotoccs.com")
        self.assertEqual(profile.office_location, active_office)
        self.assertEqual(profile.city, "Appleton")
        self.assertIn("office_location", response.context["employee_form"].errors)

    def test_invalid_user_form_does_not_save_employee_form(self):
        office = self.make_office("Appleton")
        user = self.make_user(username="profileuser", email="original@gotoccs.com")
        profile = self.make_profile(user=user, office_location=office, city="Appleton")
        self.login(user)

        response = self.client.post(
            reverse("profile"),
            self.profile_data(office, email="not-an-email", city="Changed City"),
        )

        user.refresh_from_db()
        profile.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(user.email, "original@gotoccs.com")
        self.assertEqual(profile.city, "Appleton")
        self.assertIn("email", response.context["user_form"].errors)


class PreferencesViewTests(AccountsViewTestCase):
    def test_preferences_requires_login(self):
        self.assert_login_required(reverse("preferences"))

    def test_preferences_get_creates_default_record(self):
        user = self.make_user(username="prefsuser")
        self.login(user)

        response = self.client.get(reverse("preferences"))

        preference = UserPreference.objects.get(user=user)
        self.assertEqual(preference.color_scheme, UserPreference.ColorScheme.DEFAULT)
        self.assertEqual(preference.theme, UserPreference.Theme.AUTO)
        self.assertEqual(response.context["form"].instance, preference)
        self.assertTemplateUsed(response, "accounts/preferences.html")

    def test_preferences_get_uses_existing_record(self):
        user = self.make_user(username="prefsuser")
        preference = UserPreference.objects.create(
            user=user,
            color_scheme=UserPreference.ColorScheme.FOREST,
            theme=UserPreference.Theme.DARK,
        )
        self.login(user)

        response = self.client.get(reverse("preferences"))

        self.assertEqual(response.context["form"].instance, preference)
        self.assertEqual(response.context["form"].initial["color_scheme"], UserPreference.ColorScheme.FOREST)
        self.assertEqual(response.context["form"].initial["theme"], UserPreference.Theme.DARK)

    def test_valid_preferences_post_updates_record(self):
        user = self.make_user(username="prefsuser")
        self.login(user)

        response = self.client.post(
            reverse("preferences"),
            {
                "color_scheme": UserPreference.ColorScheme.CRIMSON,
                "theme": UserPreference.Theme.LIGHT,
            },
            follow=True,
        )

        preference = UserPreference.objects.get(user=user)
        self.assertRedirects(response, reverse("preferences"))
        self.assertEqual(preference.color_scheme, UserPreference.ColorScheme.CRIMSON)
        self.assertEqual(preference.theme, UserPreference.Theme.LIGHT)
        self.assertIn("Preferences saved.", self.messages_for(response))

    def test_invalid_preferences_post_keeps_existing_values(self):
        user = self.make_user(username="prefsuser")
        preference = UserPreference.objects.create(
            user=user,
            color_scheme=UserPreference.ColorScheme.GOLD,
            theme=UserPreference.Theme.DARK,
        )
        self.login(user)

        response = self.client.post(
            reverse("preferences"),
            {"color_scheme": "invalid", "theme": "invalid"},
        )

        preference.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(preference.color_scheme, UserPreference.ColorScheme.GOLD)
        self.assertEqual(preference.theme, UserPreference.Theme.DARK)
        self.assertIn("color_scheme", response.context["form"].errors)
        self.assertIn("theme", response.context["form"].errors)
