import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_seed_office_locations"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="employeeprofile",
            name="supervisor",
            field=models.ForeignKey(
                blank=True,
                help_text="Project manager responsible for approving this employee's timesheets.",
                limit_choices_to={"groups__name": "ProjectManagers"},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="direct_reports",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
