import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("timesheets", "0003_remove_partentry_unit_cost_currency"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TimesheetReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to="timesheet_receipts/%Y/%m/")),
                ("original_filename", models.CharField(max_length=255)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("timesheet", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="receipts", to="timesheets.timesheet")),
                ("uploaded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="uploaded_timesheet_receipts", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-uploaded_at"],
            },
        ),
    ]
