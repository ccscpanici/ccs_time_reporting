from django.core.management.base import BaseCommand
from timesheets.services.defaults import seed_management_group, seed_project_managers_group, seed_mileage_rates, seed_office_locations, seed_work_codes


class Command(BaseCommand):
    help = "Seed default CCS work codes, mileage rates, office locations, and the Management Staff group. Safe to run multiple times."

    def handle(self, *args, **options):
        seed_work_codes(stdout=self.stdout)
        seed_mileage_rates(stdout=self.stdout)
        seed_office_locations(stdout=self.stdout)
        seed_management_group(stdout=self.stdout)
        seed_project_managers_group(stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS("Default data seed complete."))
