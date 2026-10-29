from django.db import migrations, models
import django.db.models.expressions


class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_employeeprofile_birthday")]

    operations = [
        migrations.CreateModel(
            name="CompanyOverhead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("frequency", models.CharField(choices=[("monthly", "Monthly"), ("annual", "Annual")], default="monthly", max_length=10)),
                ("effective_start", models.DateField()),
                ("effective_end", models.DateField(blank=True, null=True)),
                ("active", models.BooleanField(default=True)),
            ],
            options={"verbose_name": "Company Overhead", "verbose_name_plural": "Company Overhead", "ordering": ["name", "-effective_start", "pk"]},
        ),
        migrations.AddConstraint(
            model_name="companyoverhead",
            constraint=models.CheckConstraint(condition=models.Q(amount__gte=0), name="accounts_overhead_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="companyoverhead",
            constraint=models.CheckConstraint(
                condition=models.Q(effective_end__isnull=True) | models.Q(effective_end__gte=models.F("effective_start")),
                name="accounts_overhead_valid_dates",
            ),
        ),
    ]
