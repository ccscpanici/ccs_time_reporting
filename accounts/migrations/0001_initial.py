# Generated starter migration for employee metadata and office locations.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="OfficeLocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
                ("address_1", models.CharField(max_length=255)),
                ("address_2", models.CharField(blank=True, max_length=255)),
                ("city", models.CharField(max_length=100)),
                ("state", models.CharField(max_length=50)),
                ("postal_code", models.CharField(max_length=20)),
                ("active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="EmployeeProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("employee_code", models.CharField(blank=True, max_length=30, null=True, unique=True)),
                ("title", models.CharField(blank=True, max_length=100)),
                ("department", models.CharField(blank=True, max_length=100)),
                ("address_1", models.CharField(blank=True, max_length=255)),
                ("address_2", models.CharField(blank=True, max_length=255)),
                ("city", models.CharField(blank=True, max_length=100)),
                ("state", models.CharField(blank=True, max_length=50)),
                ("postal_code", models.CharField(blank=True, max_length=20)),
                ("country", models.CharField(blank=True, default="USA", max_length=100)),
                ("office_location", models.ForeignKey(blank=True, help_text="Company office this employee is assigned to.", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="employees", to="accounts.officelocation")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="employee_profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="UserPreference",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("color_scheme", models.CharField(choices=[("default", "Default Blue"), ("slate", "Slate"), ("forest", "Forest"), ("crimson", "Crimson"), ("gold", "Gold")], default="default", max_length=20)),
                ("theme", models.CharField(choices=[("auto", "Auto"), ("light", "Light"), ("dark", "Dark")], default="auto", max_length=10)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="preferences", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
