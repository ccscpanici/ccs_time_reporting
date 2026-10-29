from decimal import Decimal
from django.db import migrations, models
import django.db.models.deletion


def seed_existing_profiles(apps, schema_editor):
    EmployeeProfile = apps.get_model("accounts", "EmployeeProfile")
    Financial = apps.get_model("accounts", "EmployeeFinancialProfile")
    alias = schema_editor.connection.alias
    for employee_id in EmployeeProfile.objects.using(alias).values_list("pk", flat=True).iterator():
        Financial.objects.using(alias).get_or_create(employee_id=employee_id)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0006_company_overhead")]

    operations = [
        migrations.CreateModel(
            name="EmployeeFinancialProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("annual_salary", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("employer_payroll_taxes", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("annual_benefits", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("employer_401k", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("annual_bonuses", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("other_annual_costs", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("include_in_overhead", models.BooleanField(default=True)),
                ("annual_working_hours", models.DecimalField(decimal_places=2, default=2080, max_digits=8)),
                ("customer_billing_rate", models.DecimalField(decimal_places=2, default=140, max_digits=9)),
                ("employee", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="financial_profile", to="accounts.employeeprofile")),
            ],
            options={"verbose_name": "Employee Financial Profile", "verbose_name_plural": "Employee Financial Profiles"},
        ),
        migrations.AddConstraint(model_name="employeefinancialprofile", constraint=models.CheckConstraint(condition=models.Q(annual_salary__gte=0), name="acct_fin_salary_gte0")),
        migrations.AddConstraint(model_name="employeefinancialprofile", constraint=models.CheckConstraint(condition=models.Q(employer_payroll_taxes__gte=0), name="acct_fin_taxes_gte0")),
        migrations.AddConstraint(model_name="employeefinancialprofile", constraint=models.CheckConstraint(condition=models.Q(annual_benefits__gte=0), name="acct_fin_benefits_gte0")),
        migrations.AddConstraint(model_name="employeefinancialprofile", constraint=models.CheckConstraint(condition=models.Q(employer_401k__gte=0), name="acct_fin_401k_gte0")),
        migrations.AddConstraint(model_name="employeefinancialprofile", constraint=models.CheckConstraint(condition=models.Q(annual_bonuses__gte=0), name="acct_fin_bonus_gte0")),
        migrations.AddConstraint(model_name="employeefinancialprofile", constraint=models.CheckConstraint(condition=models.Q(other_annual_costs__gte=0), name="acct_fin_other_gte0")),
        migrations.AddConstraint(model_name="employeefinancialprofile", constraint=models.CheckConstraint(condition=models.Q(customer_billing_rate__gte=0), name="acct_fin_billing_gte0")),
        migrations.AddConstraint(model_name="employeefinancialprofile", constraint=models.CheckConstraint(condition=models.Q(annual_working_hours__gt=0), name="acct_fin_hours_gt0")),
        migrations.RunPython(seed_existing_profiles, migrations.RunPython.noop),
    ]
