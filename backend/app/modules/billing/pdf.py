"""Sinh file PDF hóa đơn bằng reportlab.

Hàm render là CPU-bound và sync — worker gọi qua asyncio.to_thread.
TODO(pdf): đăng ký font TTF hỗ trợ tiếng Việt (vd: Roboto) — font mặc định
của reportlab (Helvetica) không render được dấu tiếng Việt.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


@dataclass(frozen=True)
class InvoicePdfLine:
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal


@dataclass(frozen=True)
class InvoicePdfData:
    invoice_code: str
    period: date
    property_name: str
    room_code: str
    due_date: date
    lines: list[InvoicePdfLine] = field(default_factory=list)
    total_amount: Decimal = Decimal("0")


def render_invoice_pdf(data: InvoicePdfData) -> bytes:
    """Vẽ hóa đơn 1 trang A4, trả về PDF bytes."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    _page_width, page_height = A4
    y = page_height - 30 * mm

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(25 * mm, y, f"HOA DON TIEN PHONG - {data.invoice_code}")
    y -= 10 * mm

    pdf.setFont("Helvetica", 11)
    pdf.drawString(25 * mm, y, f"Toa nha: {data.property_name}")
    y -= 6 * mm
    pdf.drawString(25 * mm, y, f"Phong: {data.room_code}")
    y -= 6 * mm
    pdf.drawString(25 * mm, y, f"Ky: {data.period:%m/%Y}  |  Han thanh toan: {data.due_date:%d/%m/%Y}")
    y -= 12 * mm

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(25 * mm, y, "Khoan muc")
    pdf.drawRightString(120 * mm, y, "SL")
    pdf.drawRightString(150 * mm, y, "Don gia")
    pdf.drawRightString(185 * mm, y, "Thanh tien")
    y -= 2 * mm
    pdf.line(25 * mm, y, 185 * mm, y)
    y -= 6 * mm

    pdf.setFont("Helvetica", 10)
    for line in data.lines:
        pdf.drawString(25 * mm, y, line.description)
        pdf.drawRightString(120 * mm, y, f"{line.quantity:,.2f}")
        pdf.drawRightString(150 * mm, y, f"{line.unit_price:,.0f}")
        pdf.drawRightString(185 * mm, y, f"{line.amount:,.0f}")
        y -= 6 * mm

    y -= 2 * mm
    pdf.line(25 * mm, y, 185 * mm, y)
    y -= 8 * mm
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawRightString(185 * mm, y, f"TONG CONG: {data.total_amount:,.0f} VND")

    pdf.save()
    return buffer.getvalue()
