from __future__ import annotations

import hashlib
from pathlib import Path

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

from absence.models import AbsenceArtifact
from absence.services.request_days import request_day_minutes
from absence.services.time_values import format_hhmm


def employee_initials(user) -> str:
    first = (user.first_name or "").strip()
    last = (user.last_name or "").strip()
    if first and last:
        return (first[0] + last[0]).upper()
    compact = "".join(ch for ch in user.get_username() if ch.isalnum())
    return (compact[:2] or "XX").upper()


def _unique_archive_path(request):
    root = Path(settings.ABSENCE_PDF_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    base = f"{employee_initials(request.employee)}_{request.start_date:%Y%m%d}"
    candidate = root / f"{base}.pdf"
    counter = 2
    while candidate.exists():
        candidate = root / f"{base}_{counter}.pdf"
        counter += 1
    return candidate


def _name(user):
    if not user:
        return ""
    return user.get_full_name() or user.get_username()


def _dt(value):
    if not value:
        return ""
    try:
        from django.utils import timezone
        value = timezone.localtime(value)
    except Exception:
        pass
    return value.strftime("%m/%d/%Y %I:%M %p")


def _yes_no(value):
    return "Yes" if value else "No"


def generate_absence_pdf(request, generated_by=None) -> AbsenceArtifact:
    if not request.is_final:
        raise ValueError("Only finalized absence requests can be archived.")

    path = _unique_archive_path(request)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CenteredSmall", parent=styles["Normal"], alignment=TA_CENTER, fontSize=8, leading=10))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading3"], spaceBefore=8, spaceAfter=5))

    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
        title="CCS Absence Request",
        author="Complete Control Solutions",
    )

    story = [
        Paragraph("<b>COMPLETE CONTROL SOLUTIONS</b>", styles["Title"]),
        Paragraph("ABSENCE REQUEST FORM – ABSENCE INFORMATION", styles["Heading2"]),
        Spacer(1, 0.08 * inch),
    ]

    info = [
        ["Employee Name", _name(request.employee), "Manager", _name(request.manager)],
        ["Absence Request Type", request.get_absence_type_display(), "Status", request.get_status_display()],
        ["Dates From", request.start_date.strftime("%m/%d/%Y"), "To", request.end_date.strftime("%m/%d/%Y")],
        ["Requested Time", format_hhmm(request.requested_minutes), "Late Notice", _yes_no(request.late_notice)],
        ["Vacation Added to Company Outlook Calendar", _yes_no(request.calendar_acknowledged), "", ""],
    ]
    table = Table(info, colWidths=[1.6 * inch, 2.15 * inch, 1.25 * inch, 2.0 * inch])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("BACKGROUND", (2, 0), (2, -1), colors.whitesmoke),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([table, Spacer(1, 0.12 * inch)])

    daily_values = request_day_minutes(request)
    if daily_values:
        story.append(Paragraph("REQUESTED HOURS BY WORKDAY", styles["Section"]))
        daily_rows = [["Date", "Day", "Hours"]]
        for work_date, minutes in daily_values:
            daily_rows.append([work_date.strftime("%m/%d/%Y"), work_date.strftime("%A"), format_hhmm(minutes)])
        daily_rows.append(["", "Total", format_hhmm(request.requested_minutes)])
        daily_table = Table(daily_rows, colWidths=[1.7 * inch, 2.2 * inch, 1.2 * inch])
        daily_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (1, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
        ]))
        story.extend([daily_table, Spacer(1, 0.12 * inch)])

    story.append(Paragraph("PTO BALANCE SNAPSHOT", styles["Section"]))
    pto = [
        [
            "Vacation / Year",
            f"{request.vacation_weeks_per_year_snapshot} weeks ({format_hhmm(request.annual_vacation_snapshot_minutes)})",
            "Payroll As Of",
            request.balance_as_of_snapshot.strftime("%m/%d/%Y") if request.balance_as_of_snapshot else "",
        ],
        [
            "Vacation Used (Payroll)",
            format_hhmm(request.vacation_used_snapshot_minutes),
            "Vacation Balance",
            format_hhmm(request.vacation_balance_snapshot_minutes),
        ],
        [
            "Approved Vacation Pending",
            format_hhmm(request.approved_vacation_pending_snapshot_minutes),
            "This Request",
            format_hhmm(request.requested_minutes),
        ],
        [
            "Projected After Request",
            format_hhmm(request.projected_vacation_balance_minutes),
            "Sick Available (Payroll)",
            format_hhmm(request.sick_balance_snapshot_minutes),
        ],
    ]
    pto_table = Table(pto, colWidths=[1.6 * inch, 2.15 * inch, 1.65 * inch, 1.6 * inch])
    pto_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("BACKGROUND", (2, 0), (2, -1), colors.whitesmoke),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.extend([pto_table, Spacer(1, 0.12 * inch)])

    story.append(Paragraph("EMPLOYEE ACKNOWLEDGMENT", styles["Section"]))
    employee_ack = Table([
        ["Submitted By", _name(request.submitted_by), "Submitted", _dt(request.submitted_at)],
    ], colWidths=[1.35 * inch, 2.4 * inch, 1.05 * inch, 2.2 * inch])
    employee_ack.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("BACKGROUND", (2, 0), (2, -1), colors.whitesmoke),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
    ]))
    story.extend([employee_ack, Spacer(1, 0.12 * inch)])

    story.append(Paragraph("MANAGER APPROVAL", styles["Section"]))
    manager_rows = [
        ["Decision", "Denied" if request.supervisor_denied_at else "Approved", "Manager", _name(request.supervisor_denied_by or request.supervisor_approved_by)],
        ["Decision Date", _dt(request.supervisor_denied_at or request.supervisor_approved_at), "Notes", request.supervisor_notes or ""],
    ]
    manager_table = Table(manager_rows, colWidths=[1.2 * inch, 1.55 * inch, 1.0 * inch, 3.25 * inch])
    manager_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("BACKGROUND", (2, 0), (2, -1), colors.whitesmoke),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.extend([manager_table, Spacer(1, 0.12 * inch)])

    if request.negative_balance_exception_required:
        story.append(Paragraph("ABSENCE REQUEST – EXCEPTION FOR NEGATIVE VACATION BALANCE", styles["Section"]))
        exception_rows = [
            ["Employee Acknowledged", _yes_no(request.negative_balance_acknowledged), "Unpaid Dates", f"{request.unpaid_start_date:%m/%d/%Y} to {request.unpaid_end_date:%m/%d/%Y}" if request.unpaid_start_date and request.unpaid_end_date else ""],
            ["Exception Decision", "Denied" if request.exception_denied_at else ("Approved" if request.exception_approved_at else "Pending"), "Manager", _name(request.exception_denied_by or request.exception_approved_by)],
            ["Decision Date", _dt(request.exception_denied_at or request.exception_approved_at), "Notes", request.exception_notes or ""],
        ]
        exception_table = Table(exception_rows, colWidths=[1.45 * inch, 1.65 * inch, 1.15 * inch, 2.75 * inch])
        exception_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
            ("BACKGROUND", (2, 0), (2, -1), colors.whitesmoke),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.extend([exception_table, Spacer(1, 0.12 * inch)])

    story.extend([
        Spacer(1, 0.15 * inch),
        Paragraph(
            "This document was generated from authenticated CCS Online Time Reporting actions. "
            "User identities and timestamps replace handwritten signatures.",
            styles["CenteredSmall"],
        ),
        Spacer(1, 0.08 * inch),
        Paragraph(
            "MOSINEE OFFICE: 915 Indianhead Drive, P.O. Box 40, Mosinee, WI 54455 &nbsp;&nbsp;&nbsp; "
            "APPLETON OFFICE: 3701 E Evergreen Drive, Suite 400, Appleton, WI 54913",
            styles["CenteredSmall"],
        ),
    ])
    doc.build(story)

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return AbsenceArtifact.objects.create(
        request=request,
        artifact_type=AbsenceArtifact.ArtifactType.FINAL_PDF,
        filename=path.name,
        file_path=str(path),
        generated_by=generated_by,
        sha256=digest,
    )


def ensure_final_pdf(request, generated_by=None):
    artifact = request.artifacts.filter(artifact_type=AbsenceArtifact.ArtifactType.FINAL_PDF).first()
    if artifact and Path(artifact.file_path).exists():
        return artifact
    return generate_absence_pdf(request, generated_by=generated_by)
