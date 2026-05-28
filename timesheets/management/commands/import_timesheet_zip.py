from pathlib import Path
import shutil
import tempfile
import zipfile

from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from timesheets.models import TimesheetImport
from timesheets.services.importer import import_timesheet_upload
from timesheets.views import _apply_bulk_import_status

User = get_user_model()

class Command(BaseCommand):
    help = "Import a ZIP archive of XLSX timesheets"

    def add_arguments(self, parser):
        parser.add_argument("zip_path", type=str)
        parser.add_argument("--user", required=True)
        parser.add_argument("--submitted", action="store_true")
        parser.add_argument("--approved", action="store_true")

    def handle(self, *args, **options):
        zip_path = Path(options["zip_path"])

        if not zip_path.exists():
            raise CommandError(f"ZIP file does not exist: {zip_path}")

        try:
            user = User.objects.get(username=options["user"])
        except User.DoesNotExist:
            raise CommandError(f"User not found: {options['user']}")

        submitted = options["submitted"]
        approved = options["approved"]

        self.stdout.write(self.style.SUCCESS(f"Opening ZIP: {zip_path}"))

        with zipfile.ZipFile(zip_path) as archive:
            members = [
                m for m in archive.infolist()
                if m.filename.lower().endswith(".xlsx")
            ]

            total = len(members)

            self.stdout.write(
                self.style.SUCCESS(f"Found {total} XLSX files")
            )

            imported = 0
            failed = 0

            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_dir = Path(tmp_dir)

                for index, member in enumerate(members, start=1):
                    filename = Path(member.filename).name

                    self.stdout.write("")
                    self.stdout.write(
                        f"[{index}/{total}] Importing {filename}"
                    )

                    try:
                        extract_path = tmp_dir / filename

                        with archive.open(member) as source, open(extract_path, "wb") as target:
                            shutil.copyfileobj(source, target)

                        with open(extract_path, "rb") as workbook_file:
                            upload = TimesheetImport(employee=user)

                            upload.uploaded_file.save(
                                filename,
                                File(workbook_file),
                                save=True,
                            )

                        timesheet = import_timesheet_upload(upload)

                        _apply_bulk_import_status(
                            timesheet,
                            user,
                            mark_submitted=submitted,
                            mark_approved=approved,
                        )

                        imported += 1

                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Imported: {filename}"
                            )
                        )

                    except Exception as exc:
                        failed += 1

                        self.stdout.write(
                            self.style.ERROR(
                                f"FAILED: {filename} -> {exc}"
                            )
                        )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Completed. Imported={imported} Failed={failed}"
            )
        )
