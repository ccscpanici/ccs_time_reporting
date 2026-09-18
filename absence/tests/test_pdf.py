from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from absence.models import AbsenceRequest
from absence.services.pdf import generate_absence_pdf

User = get_user_model()


class AbsencePDFTests(TestCase):
    def test_filename_uses_initials_and_first_absence_date_and_avoids_collision(self):
        employee = User.objects.create_user(username="cpanici", first_name="Christopher", last_name="Panici")
        manager = User.objects.create_user(username="manager", first_name="Mandy", last_name="Manager")
        absence = AbsenceRequest.objects.create(
            employee=employee,
            manager=manager,
            absence_type=AbsenceRequest.AbsenceType.VACATION,
            start_date=date(2026, 8, 30),
            end_date=date(2026, 9, 4),
            requested_minutes=2400,
            status=AbsenceRequest.Status.APPROVED,
            submitted_by=employee,
            submitted_at=timezone.now(),
            supervisor_approved_by=manager,
            supervisor_approved_at=timezone.now(),
            finalized_at=timezone.now(),
        )
        with TemporaryDirectory() as temp_dir, override_settings(ABSENCE_PDF_ROOT=Path(temp_dir)):
            first = generate_absence_pdf(absence, generated_by=manager)
            second = generate_absence_pdf(absence, generated_by=manager)
            self.assertEqual(first.filename, "CP_20260830.pdf")
            self.assertEqual(second.filename, "CP_20260830_2.pdf")
            self.assertTrue(Path(first.file_path).exists())
            self.assertTrue(first.sha256)
