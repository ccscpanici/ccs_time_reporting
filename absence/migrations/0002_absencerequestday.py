from django.db import migrations, models
import django.db.models.deletion


def backfill_request_days(apps, schema_editor):
    AbsenceRequest = apps.get_model("absence", "AbsenceRequest")
    AbsenceRequestDay = apps.get_model("absence", "AbsenceRequestDay")
    from datetime import timedelta

    for request in AbsenceRequest.objects.all().iterator():
        weekdays = []
        day = request.start_date
        while day <= request.end_date:
            if day.weekday() < 5:
                weekdays.append(day)
            day += timedelta(days=1)
        remaining = request.requested_minutes
        for work_date in weekdays:
            minutes = min(480, remaining) if remaining > 0 else 0
            if minutes:
                AbsenceRequestDay.objects.create(
                    request_id=request.pk,
                    work_date=work_date,
                    requested_minutes=minutes,
                )
                remaining -= minutes


class Migration(migrations.Migration):
    dependencies = [("absence", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="AbsenceRequestDay",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("work_date", models.DateField()),
                ("requested_minutes", models.PositiveIntegerField(default=480)),
                ("request", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="days", to="absence.absencerequest")),
            ],
            options={"ordering": ("work_date",)},
        ),
        migrations.AddConstraint(
            model_name="absencerequestday",
            constraint=models.UniqueConstraint(fields=("request", "work_date"), name="absence_unique_request_work_date"),
        ),
        migrations.RunPython(backfill_request_days, migrations.RunPython.noop),
    ]
