"""Gửi email báo hóa đơn phát hành cho khách thuê.

Chạy trong worker SAU khi job sinh hóa đơn hoàn tất — best-effort:
email lỗi chỉ log, không được làm fail job (hóa đơn đã tạo xong).
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.billing.models import Invoice
from app.modules.contracts.models import ContractMember
from app.shared.email import EmailSender

logger = logging.getLogger(__name__)


class InvoiceNotificationService:
    def __init__(self, session: AsyncSession, email_sender: EmailSender) -> None:
        self._session = session
        self._email = email_sender

    async def notify_issued(self, invoice_ids: list[UUID]) -> int:
        """Gửi email cho mọi thành viên đang ở của từng hóa đơn. Trả về số email đã gửi."""
        sent = 0
        for invoice_id in invoice_ids:
            invoice = await self._session.get(Invoice, invoice_id)
            if invoice is None:
                continue
            recipients = (
                await self._session.execute(
                    select(User.email, User.full_name)
                    .join(ContractMember, ContractMember.user_id == User.id)
                    .where(
                        ContractMember.contract_id == invoice.contract_id,
                        ContractMember.left_at.is_(None),
                    )
                )
            ).all()
            for email, full_name in recipients:
                try:
                    await self._email.send(
                        to=email,
                        subject=f"[SmartRoom] Hóa đơn {invoice.code} "
                        f"kỳ {invoice.period:%m/%Y}",
                        body=self._render_body(full_name, invoice),
                    )
                    sent += 1
                except Exception:  # noqa: BLE001 — email lỗi không được fail job
                    logger.exception("Gửi email tới %s thất bại", email)
        return sent

    @staticmethod
    def _render_body(full_name: str, invoice: Invoice) -> str:
        return (
            f"Chào {full_name},\n\n"
            f"Hóa đơn {invoice.code} kỳ {invoice.period:%m/%Y} đã được phát hành.\n"
            f"Tổng tiền: {invoice.total_amount:,.0f} VND\n"
            f"Hạn thanh toán: {invoice.due_date:%d/%m/%Y}\n\n"
            f"Đăng nhập SmartRoom để xem chi tiết và tải PDF hóa đơn.\n"
        )
