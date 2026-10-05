# Generated for CCS Absence Management initial implementation.
from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PTOImport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_file", models.FileField(upload_to="absence/pto_imports/%Y/%m/")),
                ("source_name", models.CharField(max_length=255)),
                ("report_date", models.DateField(blank=True, null=True)),
                ("status", models.CharField(choices=[("preview", "Preview"), ("applied", "Applied"), ("failed", "Failed")], default="preview", max_length=20)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("applied_at", models.DateTimeField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("applied_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pto_imports_applied", to=settings.AUTH_USER_MODEL)),
                ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="pto_imports_uploaded", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-uploaded_at",)},
        ),
        migrations.CreateModel(
            name="PTOAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("vacation_weeks_per_year", models.DecimalField(decimal_places=2, default=0, max_digits=5, validators=[django.core.validators.MinValueValidator(0)])),
                ("vacation_balance_minutes", models.IntegerField(default=0)),
                ("sick_balance_minutes", models.IntegerField(default=0)),
                ("vacation_used_minutes", models.IntegerField(default=0)),
                ("sick_used_minutes", models.IntegerField(default=0)),
                ("balance_as_of", models.DateField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("employee", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="pto_account", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pto_accounts_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "PTO Account",
                "verbose_name_plural": "PTO Accounts",
                "ordering": ("employee__last_name", "employee__first_name", "employee__username"),
            },
        ),
        migrations.CreateModel(
            name="AbsenceRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("absence_type", models.CharField(choices=[("vacation", "Vacation"), ("sick", "Sick"), ("personal", "Personal Time")], max_length=20)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("requested_minutes", models.PositiveIntegerField(default=0)),
                ("calendar_acknowledged", models.BooleanField(default=False)),
                ("late_notice", models.BooleanField(default=False)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("submitted", "Pending Supervisor Approval"), ("pending_exception", "Pending Negative Balance Exception Approval"), ("approved", "Approved"), ("denied", "Denied")], default="draft", max_length=30)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("vacation_weeks_per_year_snapshot", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("vacation_balance_snapshot_minutes", models.IntegerField(default=0)),
                ("sick_balance_snapshot_minutes", models.IntegerField(default=0)),
                ("balance_as_of_snapshot", models.DateField(blank=True, null=True)),
                ("projected_vacation_balance_minutes", models.IntegerField(blank=True, null=True)),
                ("negative_balance_exception_required", models.BooleanField(default=False)),
                ("negative_balance_acknowledged", models.BooleanField(default=False)),
                ("unpaid_start_date", models.DateField(blank=True, null=True)),
                ("unpaid_end_date", models.DateField(blank=True, null=True)),
                ("supervisor_approved_at", models.DateTimeField(blank=True, null=True)),
                ("supervisor_denied_at", models.DateTimeField(blank=True, null=True)),
                ("supervisor_notes", models.TextField(blank=True)),
                ("exception_approved_at", models.DateTimeField(blank=True, null=True)),
                ("exception_denied_at", models.DateTimeField(blank=True, null=True)),
                ("exception_notes", models.TextField(blank=True)),
                ("finalized_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="absence_requests", to=settings.AUTH_USER_MODEL)),
                ("exception_approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="absence_requests_exception_approved", to=settings.AUTH_USER_MODEL)),
                ("exception_denied_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="absence_requests_exception_denied", to=settings.AUTH_USER_MODEL)),
                ("manager", models.ForeignKey(blank=True, help_text="Supervisor snapshot captured when the request is submitted.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="managed_absence_requests", to=settings.AUTH_USER_MODEL)),
                ("submitted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="absence_requests_submitted", to=settings.AUTH_USER_MODEL)),
                ("supervisor_approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="absence_requests_supervisor_approved", to=settings.AUTH_USER_MODEL)),
                ("supervisor_denied_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="absence_requests_supervisor_denied", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-start_date", "-created_at")},
        ),
        migrations.CreateModel(
            name="PTOImportRow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("row_number", models.PositiveIntegerField()),
                ("employee_name", models.CharField(max_length=200)),
                ("match_status", models.CharField(choices=[("matched", "Matched"), ("unmatched", "Unmatched"), ("ambiguous", "Ambiguous"), ("invalid", "Invalid")], max_length=20)),
                ("match_message", models.CharField(blank=True, max_length=255)),
                ("sick_available_minutes", models.IntegerField(default=0)),
                ("sick_used_minutes", models.IntegerField(default=0)),
                ("vacation_available_minutes", models.IntegerField(default=0)),
                ("vacation_used_minutes", models.IntegerField(default=0)),
                ("employee", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pto_import_rows", to=settings.AUTH_USER_MODEL)),
                ("pto_import", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rows", to="absence.ptoimport")),
            ],
            options={"ordering": ("row_number",)},
        ),
        migrations.CreateModel(
            name="PTOAccountChange",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(choices=[("manual", "Manual"), ("import", "PTO Report Import")], max_length=20)),
                ("old_vacation_weeks_per_year", models.DecimalField(decimal_places=2, max_digits=5)),
                ("new_vacation_weeks_per_year", models.DecimalField(decimal_places=2, max_digits=5)),
                ("old_vacation_balance_minutes", models.IntegerField()),
                ("new_vacation_balance_minutes", models.IntegerField()),
                ("old_sick_balance_minutes", models.IntegerField()),
                ("new_sick_balance_minutes", models.IntegerField()),
                ("old_vacation_used_minutes", models.IntegerField()),
                ("new_vacation_used_minutes", models.IntegerField()),
                ("old_sick_used_minutes", models.IntegerField()),
                ("new_sick_used_minutes", models.IntegerField()),
                ("old_balance_as_of", models.DateField(blank=True, null=True)),
                ("new_balance_as_of", models.DateField(blank=True, null=True)),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                ("note", models.TextField(blank=True)),
                ("changed_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pto_account_changes", to=settings.AUTH_USER_MODEL)),
                ("pto_account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="changes", to="absence.ptoaccount")),
                ("pto_import", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="account_changes", to="absence.ptoimport")),
            ],
            options={"ordering": ("-changed_at",)},
        ),
        migrations.CreateModel(
            name="AbsenceArtifact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("artifact_type", models.CharField(choices=[("final_pdf", "Final PDF")], default="final_pdf", max_length=20)),
                ("filename", models.CharField(max_length=255)),
                ("file_path", models.CharField(max_length=1000)),
                ("generated_at", models.DateTimeField(auto_now_add=True)),
                ("sha256", models.CharField(blank=True, max_length=64)),
                ("generated_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="absence_artifacts_generated", to=settings.AUTH_USER_MODEL)),
                ("request", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="artifacts", to="absence.absencerequest")),
            ],
            options={"ordering": ("-generated_at",)},
        ),
        migrations.AddIndex(
            model_name="absencerequest",
            index=models.Index(fields=["status", "manager"], name="absence_status_mgr_idx"),
        ),
        migrations.AddIndex(
            model_name="absencerequest",
            index=models.Index(fields=["employee", "start_date"], name="absence_employee_date_idx"),
        ),
        migrations.AddConstraint(
            model_name="ptoimportrow",
            constraint=models.UniqueConstraint(fields=("pto_import", "row_number"), name="absence_unique_pto_import_row"),
        ),
    ]
