from decimal import Decimal

from django.db import migrations, models


def seed_overnight_rate(apps, schema_editor):
    OvernightRate = apps.get_model("timesheets", "OvernightRate")
    OvernightRate.objects.update_or_create(
        year=2026,
        defaults={"rate": Decimal("50.00")},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("timesheets", "0017_timesheetreopenrequest_decision_notes"),
    ]

    operations = [
        migrations.CreateModel(
            name="OvernightRate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("year", models.PositiveIntegerField(unique=True)),
                ("rate", models.DecimalField(decimal_places=2, max_digits=8)),
            ],
            options={"ordering": ["-year"]},
        ),
        migrations.AddField(
            model_name="timesheet",
            name="overnight_rate",
            field=models.DecimalField(decimal_places=2, default=Decimal("50.00"), max_digits=8),
        ),
        migrations.RunPython(seed_overnight_rate, migrations.RunPython.noop),
    ]
