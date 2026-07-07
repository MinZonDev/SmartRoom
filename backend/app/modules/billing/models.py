"""ORM models: invoices, invoice_items."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    Enum as SAEnum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.enums import InvoiceStatus


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("contract_id", "period"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contracts.id"))
    code: Mapped[str] = mapped_column(String(30), unique=True)
    period: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    status: Mapped[InvoiceStatus] = mapped_column(
        SAEnum(
            InvoiceStatus,
            name="invoice_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=InvoiceStatus.DRAFT,
    )
    issued_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    pdf_url: Mapped[str | None]
    note: Mapped[str | None]

    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    service_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("services.id"))
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("1"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    invoice: Mapped[Invoice] = relationship(back_populates="items")
