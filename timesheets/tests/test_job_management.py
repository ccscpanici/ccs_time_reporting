from datetime import date

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from .base import AppTestCase

from timesheets.models import Customer, Job


User = get_user_model()


@override_settings(USE_TZ=True)
class JobManagementTestBase(AppTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="employee",
            password="test-password",
            first_name="Regular",
            last_name="Employee",
            email="employee@gotoccs.com",
        )
        cls.lead_user = User.objects.create_user(
            username="lead",
            password="test-password",
            first_name="Alice",
            last_name="Lead",
            email="lead@gotoccs.com",
        )
        cls.engineer_user = User.objects.create_user(
            username="engineer",
            password="test-password",
            first_name="Bob",
            last_name="Engineer",
            email="engineer@gotoccs.com",
        )
        cls.customer = Customer.objects.create(name="Alpha Foods")

    def make_job(self, job_number, **overrides):
        values = {
            "customer": self.customer,
            "work_type": "Controls",
            "location": "Appleton",
            "customer_po": "PO-100",
            "quote_number": "Q-100",
        }
        values.update(overrides)
        return self.make_job_record(job_number=job_number, **values)

    def valid_form_data(self, **overrides):
        data = {
            "job_number": "26010",
            "description": "New automation project",
            "customer_name": "Beta Dairy",
            "year": "2026",
            "job_month": "8",
            "job_status": Job.STATUS_ACTIVE,
            "invoice_status": Job.INVOICE_STATUS_PROGRESS,
            "work_type": "Automation",
            "location": "Waupun",
            "customer_contact": "Jordan Smith",
            "customer_po": "PO-26010",
            "lead": "Alice Lead",
            "lead_user": str(self.lead_user.pk),
            "quote_number": "Q-26010",
            "comments": "Test job",
            "engineer_01": "Bob Engineer",
            "engineer_01_user": str(self.engineer_user.pk),
            "active": "on",
        }
        data.update(overrides)
        return data


class JobManagementPermissionTests(JobManagementTestBase):
    def test_anonymous_user_is_redirected_from_all_job_pages(self):
        job = self.make_job("26001")
        urls = [
            reverse("job_list"),
            reverse("job_create"),
            reverse("job_edit", args=[job.pk]),
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_any_authenticated_user_can_open_job_pages(self):
        job = self.make_job("26001")
        self.client.force_login(self.user)

        for url in [
            reverse("job_list"),
            reverse("job_create"),
            reverse("job_edit", args=[job.pk]),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)


class JobListTests(JobManagementTestBase):
    def setUp(self):
        self.client.force_login(self.user)

    def test_default_filter_uses_current_year(self):
        current_year = date.today().year
        current = self.make_job("26001", year=current_year)
        self.make_job("25001", year=current_year - 1)

        response = self.client.get(reverse("job_list"))

        jobs = list(response.context["page_obj"].object_list)
        self.assertEqual(jobs, [current])
        self.assertEqual(response.context["year_filter"], str(current_year))

    def test_year_all_returns_jobs_from_multiple_years(self):
        first = self.make_job("25001", year=2025)
        second = self.make_job("26001", year=2026)

        response = self.client.get(reverse("job_list"), {"year": "all", "sort": "job", "dir": "asc"})

        self.assertEqual(list(response.context["page_obj"].object_list), [first, second])

    def test_invalid_year_falls_back_to_all(self):
        self.make_job("25001", year=2025)
        self.make_job("26001", year=2026)

        response = self.client.get(reverse("job_list"), {"year": "not-a-year"})

        self.assertEqual(response.context["year_filter"], "all")
        self.assertEqual(response.context["page_obj"].paginator.count, 2)

    def test_search_matches_job_number_description_customer_po_location_and_quote(self):
        job_number_match = self.make_job(
            "26011",
            description="Packaging controls",
        )
        customer_match = self.make_job(
            "26012",
            description="Other",
            customer=Customer.objects.create(name="Target Customer"),
        )
        po_match = self.make_job(
            "26013",
            description="Other",
            customer_po="MATCH-PO",
        )
        location_match = self.make_job(
            "26014",
            description="Other",
            location="Matchville",
        )
        quote_match = self.make_job(
            "26015",
            description="Other",
            quote_number="MATCH-Q",
        )

        cases = [
            ("26011", job_number_match),
            ("packaging", job_number_match),
            ("target customer", customer_match),
            ("match-po", po_match),
            ("matchville", location_match),
            ("match-q", quote_match),
        ]

        for query, expected in cases:
            with self.subTest(query=query):
                response = self.client.get(
                    reverse("job_list"),
                    {
                        "year": "all",
                        "q": query,
                    },
                )

                self.assertEqual(
                    list(response.context["page_obj"].object_list),
                    [expected],
                )
    def test_status_filter(self):
        active = self.make_job("26001", job_status=Job.STATUS_ACTIVE)
        self.make_job("26002", job_status=Job.STATUS_COMPLETE)

        response = self.client.get(reverse("job_list"), {"year": "all", "status": Job.STATUS_ACTIVE})

        self.assertEqual(list(response.context["page_obj"].object_list), [active])

    def test_active_and_inactive_filters(self):
        active = self.make_job("26001", active=True)
        inactive = self.make_job("26002", active=False)

        active_response = self.client.get(reverse("job_list"), {"year": "all", "active": "active"})
        inactive_response = self.client.get(reverse("job_list"), {"year": "all", "active": "inactive"})

        self.assertEqual(list(active_response.context["page_obj"].object_list), [active])
        self.assertEqual(list(inactive_response.context["page_obj"].object_list), [inactive])

    def test_default_job_sort_is_descending(self):
        low = self.make_job("26001")
        high = self.make_job("26020")

        response = self.client.get(reverse("job_list"), {"year": "all"})

        self.assertEqual(list(response.context["page_obj"].object_list), [high, low])
        self.assertEqual(response.context["sort_field"], "job")
        self.assertEqual(response.context["sort_dir"], "desc")

    def test_description_and_customer_sorting(self):
        zulu = self.make_job("26001", description="Zulu", customer=Customer.objects.create(name="Beta"))
        alpha = self.make_job("26002", description="Alpha", customer=Customer.objects.create(name="Alpha"))

        by_description = self.client.get(reverse("job_list"), {"year": "all", "sort": "description", "dir": "asc"})
        by_customer = self.client.get(reverse("job_list"), {"year": "all", "sort": "customer", "dir": "asc"})

        self.assertEqual(list(by_description.context["page_obj"].object_list), [alpha, zulu])
        self.assertEqual(list(by_customer.context["page_obj"].object_list), [alpha, zulu])

    def test_invalid_sort_and_direction_use_defaults(self):
        low = self.make_job("26001")
        high = self.make_job("26002")

        response = self.client.get(reverse("job_list"), {"year": "all", "sort": "bogus", "dir": "sideways"})

        self.assertEqual(response.context["sort_field"], "job")
        self.assertEqual(response.context["sort_dir"], "desc")
        self.assertEqual(list(response.context["page_obj"].object_list), [high, low])

    def test_pagination_uses_fifty_jobs_per_page(self):
        for number in range(1, 56):
            self.make_job(f"26{number:03d}")

        first_page = self.client.get(reverse("job_list"), {"year": "all", "sort": "job", "dir": "asc"})
        second_page = self.client.get(reverse("job_list"), {"year": "all", "sort": "job", "dir": "asc", "page": 2})

        self.assertEqual(len(first_page.context["page_obj"].object_list), 50)
        self.assertEqual(len(second_page.context["page_obj"].object_list), 5)
        self.assertEqual(first_page.context["page_obj"].paginator.count, 55)

    def test_context_contains_distinct_statuses_and_years(self):
        self.make_job("25001", year=2025, job_status=Job.STATUS_COMPLETE)
        self.make_job("26001", year=2026, job_status=Job.STATUS_ACTIVE)

        response = self.client.get(reverse("job_list"), {"year": "all"})

        self.assertEqual(list(response.context["available_years"]), [2026, 2025])
        self.assertIn(Job.STATUS_ACTIVE, list(response.context["statuses"]))
        self.assertIn(Job.STATUS_COMPLETE, list(response.context["statuses"]))


class JobCreateTests(JobManagementTestBase):
    def setUp(self):
        self.client.force_login(self.user)

    def test_get_uses_unknown_status_and_active_defaults(self):
        response = self.client.get(reverse("job_create"))

        form = response.context["form"]
        self.assertEqual(form.initial["job_status"], Job.STATUS_UNKNOWN)
        self.assertTrue(form.initial["active"])
        self.assertIsNone(response.context["job"])

    def test_valid_post_creates_job_customer_and_user_assignments(self):
        response = self.client.post(reverse("job_create"), self.valid_form_data())

        job = Job.objects.get(job_number="26010")
        self.assertEqual(job.customer.name, "Beta Dairy")
        self.assertEqual(job.lead_user, self.lead_user)
        self.assertEqual(job.engineer_01_user, self.engineer_user)
        self.assertEqual(job.year, 2026)
        self.assertEqual(job.job_month, 8)
        self.assertTrue(job.active)
        self.assertRedirects(response, reverse("job_list"))

    def test_blank_customer_leaves_customer_null(self):
        response = self.client.post(reverse("job_create"), self.valid_form_data(customer_name=""))

        job = Job.objects.get(job_number="26010")
        self.assertIsNone(job.customer)
        self.assertRedirects(response, reverse("job_list"))

    def test_existing_customer_is_reused(self):
        response = self.client.post(reverse("job_create"), self.valid_form_data(customer_name="Alpha Foods"))

        job = Job.objects.get(job_number="26010")
        self.assertEqual(job.customer, self.customer)
        self.assertEqual(Customer.objects.filter(name="Alpha Foods").count(), 1)
        self.assertRedirects(response, reverse("job_list"))

    def test_duplicate_job_number_is_rejected_case_insensitively(self):
        self.make_job("ABC2601")

        response = self.client.post(reverse("job_create"), self.valid_form_data(job_number="abc2601"))

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "job_number", "A job with this job number already exists.")
        self.assertEqual(Job.objects.filter(job_number__iexact="ABC2601").count(), 1)

    def test_blank_job_number_is_rejected(self):
        response = self.client.post(reverse("job_create"), self.valid_form_data(job_number=""))

        self.assertEqual(response.status_code, 200)
        self.assertIn("job_number", response.context["form"].errors)
        self.assertFalse(Job.objects.filter(description="New automation project").exists())

    def test_year_and_month_are_inferred_from_numeric_and_support_job_numbers(self):
        numeric_data = self.valid_form_data(job_number="27015", year="", job_month="", customer_name="")
        support_data = self.valid_form_data(job_number="SCL2804", year="", job_month="", customer_name="")

        self.client.post(reverse("job_create"), numeric_data)
        self.client.post(reverse("job_create"), support_data)

        numeric = Job.objects.get(job_number="27015")
        support = Job.objects.get(job_number="SCL2804")
        self.assertEqual((numeric.year, numeric.job_month), (2027, None))
        self.assertEqual((support.year, support.job_month), (2028, 4))


class JobEditTests(JobManagementTestBase):
    def setUp(self):
        self.client.force_login(self.user)

    def test_get_loads_existing_job_and_customer_name(self):
        job = self.make_job("26001")

        response = self.client.get(reverse("job_edit", args=[job.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["job"], job)
        self.assertEqual(response.context["form"].instance, job)
        self.assertEqual(response.context["form"].fields["customer_name"].initial, "Alpha Foods")

    def test_valid_edit_updates_job_and_assignments(self):
        job = self.make_job("26001", active=True)
        data = self.valid_form_data(
            job_number="26001",
            description="Updated description",
            customer_name="Beta Dairy",
            active="",
        )

        response = self.client.post(reverse("job_edit", args=[job.pk]), data)

        job.refresh_from_db()
        self.assertEqual(job.description, "Updated description")
        self.assertEqual(job.customer.name, "Beta Dairy")
        self.assertEqual(job.lead_user, self.lead_user)
        self.assertEqual(job.engineer_01_user, self.engineer_user)
        self.assertFalse(job.active)
        self.assertRedirects(response, reverse("job_list"))

    def test_edit_allows_same_job_number_for_same_record(self):
        job = self.make_job("26001")

        response = self.client.post(
            reverse("job_edit", args=[job.pk]),
            self.valid_form_data(job_number="26001", customer_name="Alpha Foods"),
        )

        self.assertRedirects(response, reverse("job_list"))
        self.assertEqual(Job.objects.filter(job_number="26001").count(), 1)

    def test_edit_rejects_job_number_used_by_another_job(self):
        first = self.make_job("26001")
        self.make_job("26002")

        response = self.client.post(
            reverse("job_edit", args=[first.pk]),
            self.valid_form_data(job_number="26002"),
        )

        first.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "job_number", "A job with this job number already exists.")
        self.assertEqual(first.job_number, "26001")

    def test_edit_can_clear_customer_and_user_assignments(self):
        job = self.make_job("26001", lead_user=self.lead_user, engineer_01_user=self.engineer_user)
        data = self.valid_form_data(
            job_number="26001",
            customer_name="",
            lead_user="",
            engineer_01_user="",
        )

        response = self.client.post(reverse("job_edit", args=[job.pk]), data)

        job.refresh_from_db()
        self.assertIsNone(job.customer)
        self.assertIsNone(job.lead_user)
        self.assertIsNone(job.engineer_01_user)
        self.assertRedirects(response, reverse("job_list"))

    def test_missing_job_returns_404(self):
        response = self.client.get(reverse("job_edit", args=[999999]))

        self.assertEqual(response.status_code, 404)
