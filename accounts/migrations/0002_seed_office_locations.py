from django.db import migrations


OFFICES = [
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


def seed_office_locations(apps, schema_editor):
    OfficeLocation = apps.get_model("accounts", "OfficeLocation")

    for office in OFFICES:
        OfficeLocation.objects.update_or_create(
            name=office["name"],
            defaults=office,
        )


def unseed_office_locations(apps, schema_editor):
    OfficeLocation = apps.get_model("accounts", "OfficeLocation")
    OfficeLocation.objects.filter(
        name__in=[office["name"] for office in OFFICES]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_office_locations, unseed_office_locations),
    ]
