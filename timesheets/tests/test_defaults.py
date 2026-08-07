from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import Group

from accounts.models import OfficeLocation
from timesheets.models import MileageRate, OvernightRate, WorkCode
from timesheets.services.defaults import (
    DEFAULT_MILEAGE_RATES,
    DEFAULT_OFFICE_LOCATIONS,
    DEFAULT_OVERNIGHT_RATES,
    DEFAULT_WORK_CODES,
    seed_management_group,
    seed_mileage_rates,
    seed_office_locations,
    seed_overnight_rates,
    seed_project_managers_group,
    seed_work_codes,
)
from timesheets.tests.base import AppTestCase


class WorkCodeDefaultsTests(AppTestCase):
    def setUp(self):
        WorkCode.objects.all().delete()

    def test_seed_work_codes_creates_complete_default_set(self):
        created, updated = seed_work_codes()

        self.assertEqual(created, len(DEFAULT_WORK_CODES))
        self.assertEqual(updated, 0)
        self.assertEqual(WorkCode.objects.count(), len(DEFAULT_WORK_CODES))
        for order, (code, description) in enumerate(DEFAULT_WORK_CODES, start=10):
            work_code = WorkCode.objects.get(code=code)
            self.assertEqual(work_code.description, description)
            self.assertEqual(work_code.display_order, order)
            self.assertTrue(work_code.active)

    def test_seed_work_codes_updates_managed_fields_but_preserves_other_fields(self):
        WorkCode.objects.create(
            code="1000",
            description="Old description",
            display_order=999,
            active=False,
            allows_overtime=False,
        )

        created, updated = seed_work_codes()
        work_code = WorkCode.objects.get(code="1000")

        self.assertEqual(created, len(DEFAULT_WORK_CODES) - 1)
        self.assertEqual(updated, 1)
        self.assertEqual(work_code.description, "Office")
        self.assertEqual(work_code.display_order, 10)
        self.assertTrue(work_code.active)
        self.assertFalse(work_code.allows_overtime)

    def test_seed_work_codes_is_idempotent_and_reports_counts(self):
        seed_work_codes()
        stdout = StringIO()

        created, updated = seed_work_codes(stdout=stdout)

        self.assertEqual(created, 0)
        self.assertEqual(updated, len(DEFAULT_WORK_CODES))
        self.assertIn(f"0 created, {len(DEFAULT_WORK_CODES)} updated", stdout.getvalue())


class GroupDefaultsTests(AppTestCase):
    def test_management_group_create_then_existing_paths(self):
        Group.objects.filter(name="Management Staff").delete()
        created_out = StringIO()
        existing_out = StringIO()

        self.assertTrue(seed_management_group(stdout=created_out))
        self.assertFalse(seed_management_group(stdout=existing_out))

        self.assertTrue(Group.objects.filter(name="Management Staff").exists())
        self.assertIn("created", created_out.getvalue())
        self.assertIn("already exists", existing_out.getvalue())

    def test_project_managers_group_create_then_existing_paths(self):
        Group.objects.filter(name="ProjectManagers").delete()
        created_out = StringIO()
        existing_out = StringIO()

        self.assertTrue(seed_project_managers_group(stdout=created_out))
        self.assertFalse(seed_project_managers_group(stdout=existing_out))

        self.assertTrue(Group.objects.filter(name="ProjectManagers").exists())
        self.assertIn("created", created_out.getvalue())
        self.assertIn("already exists", existing_out.getvalue())


class MileageRateDefaultsTests(AppTestCase):
    def setUp(self):
        MileageRate.objects.all().delete()

    def test_seed_mileage_rates_creates_all_years_with_decimal_values(self):
        created, updated = seed_mileage_rates()

        self.assertEqual(created, len(DEFAULT_MILEAGE_RATES))
        self.assertEqual(updated, 0)
        self.assertEqual(MileageRate.objects.count(), len(DEFAULT_MILEAGE_RATES))
        self.assertEqual(MileageRate.objects.get(year=2000).rate, Decimal("0.325"))
        self.assertEqual(MileageRate.objects.get(year=2026).rate, Decimal("0.720"))

    def test_seed_mileage_rates_updates_existing_rates_and_reports_counts(self):
        MileageRate.objects.create(year=2026, rate=Decimal("0.111"))
        stdout = StringIO()

        created, updated = seed_mileage_rates(stdout=stdout)

        self.assertEqual(created, len(DEFAULT_MILEAGE_RATES) - 1)
        self.assertEqual(updated, 1)
        self.assertEqual(MileageRate.objects.get(year=2026).rate, Decimal("0.720"))
        self.assertIn("1 updated", stdout.getvalue())


class OvernightRateDefaultsTests(AppTestCase):
    def setUp(self):
        OvernightRate.objects.all().delete()

    def test_seed_overnight_rates_creates_defaults(self):
        created, updated = seed_overnight_rates()

        self.assertEqual(created, len(DEFAULT_OVERNIGHT_RATES))
        self.assertEqual(updated, 0)
        self.assertEqual(OvernightRate.objects.get(year=2026).rate, Decimal("50.00"))

    def test_seed_overnight_rates_updates_existing_rate_and_reports_counts(self):
        OvernightRate.objects.create(year=2026, rate=Decimal("42.00"))
        stdout = StringIO()

        created, updated = seed_overnight_rates(stdout=stdout)

        self.assertEqual((created, updated), (0, 1))
        self.assertEqual(OvernightRate.objects.get(year=2026).rate, Decimal("50.00"))
        self.assertIn("0 created, 1 updated", stdout.getvalue())


class OfficeLocationDefaultsTests(AppTestCase):
    def setUp(self):
        OfficeLocation.objects.all().delete()

    def test_seed_office_locations_creates_complete_default_set(self):
        created, updated = seed_office_locations()

        self.assertEqual(created, len(DEFAULT_OFFICE_LOCATIONS))
        self.assertEqual(updated, 0)
        self.assertEqual(OfficeLocation.objects.count(), len(DEFAULT_OFFICE_LOCATIONS))

        appleton = OfficeLocation.objects.get(name="Appleton Office")
        self.assertEqual(appleton.address_1, "3701 E. Evergreen Dr.")
        self.assertEqual(appleton.address_2, "Suite 400")
        self.assertEqual(appleton.city, "Appleton")
        self.assertEqual(appleton.state, "WI")
        self.assertEqual(appleton.postal_code, "54913")
        self.assertTrue(appleton.active)

    def test_seed_office_locations_updates_existing_location_and_reports_counts(self):
        OfficeLocation.objects.create(
            name="Mosinee Office",
            address_1="Old",
            city="Old City",
            state="XX",
            postal_code="00000",
            active=False,
        )
        stdout = StringIO()

        created, updated = seed_office_locations(stdout=stdout)
        mosinee = OfficeLocation.objects.get(name="Mosinee Office")

        self.assertEqual(created, len(DEFAULT_OFFICE_LOCATIONS) - 1)
        self.assertEqual(updated, 1)
        self.assertEqual(mosinee.address_1, "915 Indianhead Drive")
        self.assertEqual(mosinee.city, "Mosinee")
        self.assertEqual(mosinee.state, "WI")
        self.assertEqual(mosinee.postal_code, "54455")
        self.assertTrue(mosinee.active)
        self.assertIn("1 updated", stdout.getvalue())

    def test_seed_office_locations_is_idempotent(self):
        seed_office_locations()

        created, updated = seed_office_locations()

        self.assertEqual(created, 0)
        self.assertEqual(updated, len(DEFAULT_OFFICE_LOCATIONS))
