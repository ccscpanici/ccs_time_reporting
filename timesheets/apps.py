from django.apps import AppConfig
from django.db.models.signals import post_migrate


class TimesheetsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "timesheets"

    def ready(self):
        post_migrate.connect(seed_defaults_after_migrate, sender=self)


def seed_defaults_after_migrate(sender, **kwargs):
    # Run after migrations so a fresh install has usable dropdown values right away.
    # This is idempotent, so repeated migrate calls are safe.
    from timesheets.services.defaults import seed_management_group, seed_mileage_rates, seed_work_codes

    seed_work_codes()
    seed_mileage_rates()
    seed_management_group()
