from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_accountnotificationrecipient"),
    ]

    operations = [
        migrations.AddField(
            model_name="employeeprofile",
            name="birthday",
            field=models.DateField(
                blank=True,
                null=True,
                help_text="Optional employee date of birth; visible to authorized administrators.",
            ),
        ),
    ]
