from django.db import migrations, models
import re


def infer_job_year_and_month(job_number):
    raw = (job_number or "").strip().upper()
    if not raw:
        return None, None

    support_match = re.match(r"^[A-Z]+(\d{2})(\d{2})(?:\D|$)", raw)
    if support_match:
        yy = int(support_match.group(1))
        month = int(support_match.group(2))
        if 1 <= month <= 12:
            return 2000 + yy, month
        return 2000 + yy, None

    numeric_match = re.match(r"^(\d{2})", raw)
    if numeric_match:
        return 2000 + int(numeric_match.group(1)), None

    return None, None


def backfill_job_year_month(apps, schema_editor):
    Job = apps.get_model("timesheets", "Job")
    for job in Job.objects.all():
        inferred_year, inferred_month = infer_job_year_and_month(job.job_number)

        update_fields = []
        if job.year is not None and 0 <= job.year < 100:
            job.year = 2000 + job.year
            update_fields.append("year")
        elif job.year is None and inferred_year is not None:
            job.year = inferred_year
            update_fields.append("year")

        if job.job_month is None and inferred_month is not None:
            job.job_month = inferred_month
            update_fields.append("job_month")

        if update_fields:
            job.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ("timesheets", "0010_job_status_choices"),
    ]

    operations = [
        migrations.AlterField(
            model_name="job",
            name="year",
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="job",
            name="job_month",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_job_year_month, migrations.RunPython.noop),
        migrations.AlterModelOptions(
            name="job",
            options={"ordering": ["-year", "job_number"]},
        ),
    ]
