import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("timesheets", "0006_timesheet_rejection_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ActiveProject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("job_number", models.CharField(max_length=50)),
                ("budgeted_hours", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=10)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="active_projects_created", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="active_projects_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["job_number"],
                "constraints": [models.UniqueConstraint(fields=("job_number",), name="unique_active_project_job_number")],
            },
        ),
    ]
