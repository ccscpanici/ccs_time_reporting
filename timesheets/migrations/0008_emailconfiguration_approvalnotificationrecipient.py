from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("timesheets", "0007_activeproject"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailConfiguration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(default="Default", max_length=100)),
                ("from_email", models.EmailField(default="vw@gotoccs.com", max_length=254)),
                ("reply_to_email", models.EmailField(blank=True, default="admin@gotoccs.com", max_length=254)),
                ("smtp_host", models.CharField(default="smtp.office365.com", max_length=255)),
                ("smtp_port", models.PositiveIntegerField(default=587)),
                ("smtp_username", models.CharField(blank=True, default="vw@gotoccs.com", max_length=255)),
                ("smtp_password", models.CharField(blank=True, max_length=255)),
                ("use_tls", models.BooleanField(default=True)),
                ("use_ssl", models.BooleanField(default=False)),
                ("test_recipient", models.EmailField(blank=True, max_length=254)),
                ("active", models.BooleanField(default=True)),
                ("last_test_sent_at", models.DateTimeField(blank=True, null=True)),
                ("last_test_success", models.BooleanField(blank=True, null=True)),
                ("last_test_message", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Email Configuration",
                "verbose_name_plural": "Email Configuration",
            },
        ),
        migrations.CreateModel(
            name="ApprovalNotificationRecipient",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(blank=True, max_length=100)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["email"],
            },
        ),
    ]
