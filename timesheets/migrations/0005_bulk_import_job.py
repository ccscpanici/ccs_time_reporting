from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ("timesheets", "0004_timesheetreceipt"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BulkImportJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uploaded_zip", models.FileField(upload_to="bulk_imports/")),
                ("status", models.CharField(choices=[("pending","Pending"),("running","Running"),("completed","Completed"),("failed","Failed")], default="pending", max_length=20)),
                ("total_files", models.PositiveIntegerField(default=0)),
                ("processed_files", models.PositiveIntegerField(default=0)),
                ("imported_files", models.PositiveIntegerField(default=0)),
                ("failed_files", models.PositiveIntegerField(default=0)),
                ("results_json", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bulk_import_jobs", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]