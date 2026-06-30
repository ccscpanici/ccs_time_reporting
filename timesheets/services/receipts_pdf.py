from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def _add_text_page(pdf_writer, title, message):
    stream = BytesIO()
    page = canvas.Canvas(stream, pagesize=letter)
    width, height = letter

    page.setFont("Helvetica-Bold", 14)
    page.drawString(72, height - 72, title)

    page.setFont("Helvetica", 10)
    text = page.beginText(72, height - 100)
    for line in message.splitlines():
        text.textLine(line)
    page.drawText(text)

    page.showPage()
    page.save()
    stream.seek(0)

    pdf_writer.add_page(PdfReader(stream).pages[0])


def _add_image_receipt_page(pdf_writer, receipt, receipt_bytes):
    stream = BytesIO()
    page = canvas.Canvas(stream, pagesize=letter)
    width, height = letter

    page.setFont("Helvetica-Bold", 12)
    page.drawString(36, height - 36, receipt.filename())

    if receipt.description:
        page.setFont("Helvetica", 9)
        page.drawString(36, height - 52, receipt.description[:120])

    image = ImageReader(BytesIO(receipt_bytes))
    image_width, image_height = image.getSize()

    max_width = width - 72
    max_height = height - 100
    scale = min(max_width / image_width, max_height / image_height)

    draw_width = image_width * scale
    draw_height = image_height * scale
    x = (width - draw_width) / 2
    y = 36

    page.drawImage(
        image,
        x,
        y,
        width=draw_width,
        height=draw_height,
        preserveAspectRatio=True,
        anchor="c",
    )

    page.showPage()
    page.save()
    stream.seek(0)

    pdf_writer.add_page(PdfReader(stream).pages[0])


def build_receipts_pdf_bytes(timesheet):
    """Return bytes for one combined PDF containing all receipts on a timesheet."""
    receipts = list(timesheet.receipts.all().order_by("uploaded_at", "pk"))
    pdf_writer = PdfWriter()

    if not receipts:
        _add_text_page(
            pdf_writer,
            "No receipts",
            f"No receipts have been uploaded for timesheet week {timesheet.week_start}.",
        )

    for receipt in receipts:
        filename = receipt.filename()
        extension = Path(filename).suffix.lower()

        try:
            with receipt.file.open("rb") as receipt_file:
                receipt_bytes = receipt_file.read()

            if extension == ".pdf":
                receipt_pdf = PdfReader(BytesIO(receipt_bytes))
                for page in receipt_pdf.pages:
                    pdf_writer.add_page(page)
            elif extension in {".png", ".jpg", ".jpeg", ".webp"}:
                _add_image_receipt_page(pdf_writer, receipt, receipt_bytes)
            else:
                _add_text_page(
                    pdf_writer,
                    f"Unsupported receipt file: {filename}",
                    "This receipt could not be embedded in the combined PDF.\n"
                    "Please view or download the original receipt file from the timesheet.",
                )
        except Exception as exc:
            _add_text_page(
                pdf_writer,
                f"Receipt error: {filename}",
                f"This receipt could not be added to the combined PDF.\n\nError: {exc}",
            )

    output = BytesIO()
    pdf_writer.write(output)
    return output.getvalue()


def receipts_pdf_filename(timesheet):
    employee = timesheet.employee
    full_name = employee.get_full_name().strip()

    if full_name:
        initials = "".join(part[0].upper() for part in full_name.split() if part)
    else:
        initials = employee.get_username()[:2].upper()

    return f"{initials}_{timesheet.week_start:%Y%m%d}_receipts.pdf"
