DEFAULT_WORK_CODES = [
    ("1000", "Office"),
    ("1200", "Vacation"),
    ("1300", "Sick / Personal Time"),
    ("1400", "Sales/Marketing & R/D"),
    ("1500", "Warranty Work"),
    ("1600", "Travel Time"),
    ("1700", "Training"),
    ("1800", "Employee Development"),
    ("2200", "Technician Labor - Shop"),
    ("2400", "Technician Labor - Field"),
    ("4000", "Testing"),
    ("4200", "PLC Programming"),
    ("4400", "HMI/SCADA Programming"),
    ("4700", "Project Management"),
    ("4800", "Electrical Design/Eng"),
    ("4900", "Drafting"),
]


def seed_work_codes(*, stdout=None):
    """Create/update the default CCS work codes.

    Safe to run multiple times. Existing admin edits to fields not listed here
    are preserved; code, description, display_order, and active are normalized.
    """
    from timesheets.models import WorkCode

    created = 0
    updated = 0
    for display_order, (code, description) in enumerate(DEFAULT_WORK_CODES, start=10):
        _, was_created = WorkCode.objects.update_or_create(
            code=code,
            defaults={
                "description": description,
                "display_order": display_order,
                "active": True,
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1

    if stdout:
        stdout.write(f"Work codes seeded: {created} created, {updated} updated.")

    return created, updated


def seed_management_group(*, stdout=None):
    from django.contrib.auth.models import Group

    _, created = Group.objects.get_or_create(name="Management Staff")
    if stdout:
        stdout.write("Management Staff group created." if created else "Management Staff group already exists.")
    return created


def seed_project_managers_group(*, stdout=None):
    from django.contrib.auth.models import Group

    _, created = Group.objects.get_or_create(name="ProjectManagers")
    if stdout:
        stdout.write("ProjectManagers group created." if created else "ProjectManagers group already exists.")
    return created


DEFAULT_MILEAGE_RATES = {
    2000: "0.325",
    2001: "0.345",
    2002: "0.365",
    2003: "0.360",
    2004: "0.375",
    2005: "0.405",
    2006: "0.445",
    2007: "0.485",
    2008: "0.505",
    2009: "0.550",
    2010: "0.500",
    2011: "0.555",
    2012: "0.555",
    2013: "0.565",
    2014: "0.560",
    2015: "0.575",
    2016: "0.540",
    2017: "0.535",
    2018: "0.545",
    2019: "0.580",
    2020: "0.575",
    2021: "0.560",
    2022: "0.625",
    2023: "0.655",
    2024: "0.670",
    2025: "0.700",
    2026: "0.720",
}


def seed_mileage_rates(*, stdout=None):
    """Create/update yearly mileage rates from 2000 through 2026.

    Safe to run multiple times. Admins can edit rates from Django Admin after seeding.
    """
    from decimal import Decimal
    from timesheets.models import MileageRate

    created = 0
    updated = 0
    for year, rate in DEFAULT_MILEAGE_RATES.items():
        _, was_created = MileageRate.objects.update_or_create(
            year=year,
            defaults={"rate": Decimal(rate)},
        )
        if was_created:
            created += 1
        else:
            updated += 1

    if stdout:
        stdout.write(f"Mileage rates seeded: {created} created, {updated} updated.")

    return created, updated


DEFAULT_OFFICE_LOCATIONS = [
    {
        "name": "Mosinee Office",
        "address_1": "915 Indianhead Drive",
        "address_2": "",
        "city": "Mosinee",
        "state": "WI",
        "postal_code": "54455",
        "active": True,
    },
    {
        "name": "Appleton Office",
        "address_1": "3701 E. Evergreen Dr.",
        "address_2": "Suite 400",
        "city": "Appleton",
        "state": "WI",
        "postal_code": "54913",
        "active": True,
    },
]


def seed_office_locations(*, stdout=None):
    """Create/update CCS office locations. Safe to run multiple times."""
    from accounts.models import OfficeLocation

    created = 0
    updated = 0
    for office in DEFAULT_OFFICE_LOCATIONS:
        _, was_created = OfficeLocation.objects.update_or_create(
            name=office["name"],
            defaults={
                "address_1": office["address_1"],
                "address_2": office["address_2"],
                "city": office["city"],
                "state": office["state"],
                "postal_code": office["postal_code"],
                "active": office["active"],
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1

    if stdout:
        stdout.write(f"Office locations seeded: {created} created, {updated} updated.")

    return created, updated
