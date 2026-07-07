"""Business logic module billing.

Hai service tách biệt theo nơi thực thi:
- BillingCommandService  : chạy trong API process — chỉ validate + đẩy task vào queue.
- InvoiceGenerationService: chạy trong worker process — tính toán nặng + sinh PDF.
"""

import asyncio
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.billing.models import Invoice, InvoiceItem
from app.modules.billing.pdf import (
    InvoicePdfData,
    InvoicePdfLine,
    render_invoice_pdf,
)
from app.modules.billing.schemas import BillingTaskMessage
from app.modules.contracts.models import Contract, ContractMember
from app.modules.properties.models import (
    MeterReading,
    Property,
    Room,
    UtilityService,
)
from app.shared.enums import ContractStatus, InvoiceStatus, ServiceChargeType
from app.shared.exceptions import (
    MissingMeterReadingError,
    NotFoundError,
    PermissionDeniedError,
)
from app.shared.job_tracker import JobTracker
from app.shared.messaging import MessagePublisher
from app.shared.storage import FileStorage


class InvoiceQueryService:
    """Đọc hóa đơn cho chủ nhà (ownership check qua contract -> room -> property)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_invoices(
        self, owner_id: UUID, property_id: UUID
    ) -> list[Invoice]:
        result = await self._session.scalars(
            select(Invoice)
            .join(Contract, Invoice.contract_id == Contract.id)
            .join(Room, Contract.room_id == Room.id)
            .join(Property, Room.property_id == Property.id)
            .where(Property.owner_id == owner_id, Room.property_id == property_id)
            .options(selectinload(Invoice.items))
            .order_by(Invoice.period.desc(), Invoice.code)
        )
        return list(result.all())

    async def get_owned_invoice(self, owner_id: UUID, invoice_id: UUID) -> Invoice:
        invoice = await self._session.scalar(
            select(Invoice)
            .join(Contract, Invoice.contract_id == Contract.id)
            .join(Room, Contract.room_id == Room.id)
            .join(Property, Room.property_id == Property.id)
            .where(Invoice.id == invoice_id, Property.owner_id == owner_id)
        )
        if invoice is None:
            raise NotFoundError("Hóa đơn không tồn tại hoặc bạn không có quyền")
        return invoice


class BillingCommandService:
    """Nhận lệnh 'Chốt tháng' từ API: validate rồi đẩy task — KHÔNG tính toán nặng."""

    def __init__(
        self,
        session: AsyncSession,
        publisher: MessagePublisher,
        tracker: JobTracker,
    ) -> None:
        self._session = session
        self._publisher = publisher
        self._tracker = tracker

    async def close_month(
        self, *, property_id: UUID, period: date, requested_by: UUID
    ) -> str:
        prop = await self._session.get(Property, property_id)
        if prop is None:
            raise NotFoundError(f"Không tìm thấy tòa nhà {property_id}")
        if prop.owner_id != requested_by:
            raise PermissionDeniedError("Bạn không phải chủ sở hữu tòa nhà này")

        job_id = str(uuid4())
        message = BillingTaskMessage(
            job_id=job_id,
            property_id=property_id,
            period=period,
            requested_by=requested_by,
        )
        # Tạo job status TRƯỚC khi publish để client không gặp 404 khi poll ngay
        await self._tracker.create(
            job_id,
            meta={
                "property_id": str(property_id),
                "property_name": prop.name,
                "period": period.isoformat(),
            },
        )
        await self._publisher.publish(message.model_dump(mode="json"))
        return job_id


@dataclass
class BillingRunSummary:
    """Kết quả một lần chạy chốt tháng — lưu vào job tracker cho frontend hiển thị."""

    invoices_created: int = 0
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


class InvoiceGenerationService:
    """Sinh hóa đơn cho toàn bộ hợp đồng active của một tòa nhà (chạy trong worker).

    Idempotent: hợp đồng đã có hóa đơn trong kỳ sẽ bị bỏ qua, nên SQS
    redeliver message (at-least-once) không tạo hóa đơn trùng.
    """

    def __init__(self, session: AsyncSession, storage: FileStorage) -> None:
        self._session = session
        self._storage = storage

    async def generate_for_property(
        self, property_id: UUID, period: date
    ) -> BillingRunSummary:
        summary = BillingRunSummary()
        prop = await self._session.get(Property, property_id)
        if prop is None:
            raise NotFoundError(f"Không tìm thấy tòa nhà {property_id}")

        services = await self._get_active_services(property_id)
        contracts = await self._get_active_contracts(property_id)

        for contract in contracts:
            if await self._invoice_exists(contract.id, period):
                summary.skipped.append(f"{contract.code}: đã có hóa đơn kỳ này")
                continue
            try:
                invoice = await self._create_invoice(contract, services, period)
                await self._attach_pdf(invoice, contract, prop.name)
                summary.invoices_created += 1
            except MissingMeterReadingError as exc:
                # Thiếu chỉ số 1 phòng không được chặn cả tòa nhà
                summary.errors.append(f"{contract.code}: {exc}")

        await self._session.commit()
        return summary

    # ------------------------------------------------------------------ #
    # Tính toán hóa đơn
    # ------------------------------------------------------------------ #

    async def _create_invoice(
        self, contract: Contract, services: list[UtilityService], period: date
    ) -> Invoice:
        items: list[InvoiceItem] = [
            InvoiceItem(
                description="Tiền phòng",
                quantity=Decimal("1"),
                unit_price=contract.monthly_rent,
                amount=contract.monthly_rent,
            )
        ]
        for service in services:
            items.append(await self._build_service_item(contract, service, period))

        total = sum((item.amount for item in items), Decimal("0"))
        invoice = Invoice(
            contract_id=contract.id,
            code=f"INV-{period:%Y%m}-{contract.code}",
            period=period,
            # TODO(billing): cho phép chủ nhà cấu hình hạn thanh toán
            due_date=period.replace(day=10),
            total_amount=total,
            status=InvoiceStatus.ISSUED,
            issued_at=datetime.now(timezone.utc),
            items=items,
        )
        self._session.add(invoice)
        await self._session.flush()  # lấy invoice.id cho bước sinh PDF
        return invoice

    async def _build_service_item(
        self, contract: Contract, service: UtilityService, period: date
    ) -> InvoiceItem:
        """Tính số lượng theo charge_type của dịch vụ."""
        if service.charge_type == ServiceChargeType.PER_UNIT:
            reading = await self._get_reading(contract.room_id, service.id, period)
            if reading is None:
                raise MissingMeterReadingError(
                    f"Chưa nhập chỉ số '{service.name}' kỳ {period:%m/%Y}"
                )
            quantity = reading.current_value - reading.previous_value
        elif service.charge_type == ServiceChargeType.PER_PERSON:
            quantity = Decimal(await self._count_occupants(contract.id))
        else:  # PER_ROOM / FLAT
            quantity = Decimal("1")

        return InvoiceItem(
            service_id=service.id,
            description=service.name,
            quantity=quantity,
            unit_price=service.unit_price,
            amount=quantity * service.unit_price,
        )

    async def _attach_pdf(
        self, invoice: Invoice, contract: Contract, property_name: str
    ) -> None:
        """Render PDF (CPU-bound, chạy trong thread) rồi upload S3."""
        pdf_data = InvoicePdfData(
            invoice_code=invoice.code,
            period=invoice.period,
            property_name=property_name,
            room_code=contract.room.code,
            due_date=invoice.due_date,
            lines=[
                InvoicePdfLine(
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    amount=item.amount,
                )
                for item in invoice.items
            ],
            total_amount=invoice.total_amount,
        )
        pdf_bytes = await asyncio.to_thread(render_invoice_pdf, pdf_data)
        invoice.pdf_url = await self._storage.upload(
            key=f"invoices/{invoice.period:%Y/%m}/{invoice.code}.pdf",
            content=pdf_bytes,
            content_type="application/pdf",
        )

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    async def _get_active_contracts(self, property_id: UUID) -> list[Contract]:
        stmt = (
            select(Contract)
            .join(Room, Contract.room_id == Room.id)
            .where(
                Room.property_id == property_id,
                Contract.status == ContractStatus.ACTIVE,
            )
            # Eager-load: _attach_pdf đọc contract.room.code — lazy load trong
            # async session sẽ nổ lỗi greenlet_spawn
            .options(selectinload(Contract.room))
        )
        result = await self._session.scalars(stmt)
        return list(result.all())

    async def _get_active_services(self, property_id: UUID) -> list[UtilityService]:
        stmt = select(UtilityService).where(
            UtilityService.property_id == property_id,
            UtilityService.is_active.is_(True),
        )
        result = await self._session.scalars(stmt)
        return list(result.all())

    async def _invoice_exists(self, contract_id: UUID, period: date) -> bool:
        stmt = select(Invoice.id).where(
            Invoice.contract_id == contract_id, Invoice.period == period
        )
        return await self._session.scalar(stmt) is not None

    async def _get_reading(
        self, room_id: UUID, service_id: UUID, period: date
    ) -> MeterReading | None:
        stmt = select(MeterReading).where(
            MeterReading.room_id == room_id,
            MeterReading.service_id == service_id,
            MeterReading.period == period,
        )
        return await self._session.scalar(stmt)

    async def _count_occupants(self, contract_id: UUID) -> int:
        stmt = select(func.count()).where(
            ContractMember.contract_id == contract_id,
            ContractMember.left_at.is_(None),
        )
        return await self._session.scalar(stmt) or 0
