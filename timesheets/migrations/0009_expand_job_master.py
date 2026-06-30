from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ("timesheets", "0008_emailconfiguration_approvalnotificationrecipient"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="accepted_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="job",
            name="cfr_job_number",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="job",
            name="comments",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="job",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="job",
            name="customer_contact",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="job",
            name="customer_po",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="job",
            name="engineer_01",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="job",
            name="engineer_02",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="job",
            name="engineer_03",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="job",
            name="engineer_04",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="job",
            name="engineer_05",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="job",
            name="engineer_06",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="job",
            name="engineer_07",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="job",
            name="engineer_08",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="job",
            name="engineer_09",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="job",
            name="engineer_10",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="job",
            name="import_source",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="job",
            name="invoice_status",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="job",
            name="job_status",
            field=models.CharField(blank=True, default="Unknown Status", max_length=100),
        ),
        migrations.AddField(
            model_name="job",
            name="job_type",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="job",
            name="last_imported_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="job",
            name="lead",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="job",
            name="location",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="job",
            name="quote_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="job",
            name="quote_number",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="job",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, default=timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="job",
            name="work_type",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="job",
            name="year",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AlterModelOptions(
            name="job",
            options={"ordering": ["job_number"]},
        ),
    ]
