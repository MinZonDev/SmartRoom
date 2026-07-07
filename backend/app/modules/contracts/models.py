"""ORM models: contracts, contract_members."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.properties.models import Room
from app.shared.enums import ContractStatus


class Contract(Base):
    __tablename__ = "contracts"
    __table_args__ = (
        # 1 phòng chỉ có 1 hợp đồng active — chốt chặn race condition ở DB
        Index(
            "uq_contracts_one_active_per_room",
            "room_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id"))
    code: Mapped[str] = mapped_column(String(30), unique=True)
    deposit_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    monthly_rent: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    billing_day: Mapped[int] = mapped_column(SmallInteger, default=1)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[ContractStatus] = mapped_column(
        SAEnum(
            ContractStatus,
            name="contract_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=ContractStatus.PENDING,
    )
    note: Mapped[str | None]

    room: Mapped[Room] = relationship()
    members: Mapped[list["ContractMember"]] = relationship(back_populates="contract")


class ContractMember(Base):
    """Người ở trong hợp đồng — hỗ trợ ghép phòng (N khách thuê / 1 hợp đồng)."""

    __tablename__ = "contract_members"
    __table_args__ = (
        UniqueConstraint("contract_id", "user_id"),
        # Mỗi hợp đồng chỉ có 1 người đại diện
        Index(
            "uq_contract_members_one_primary",
            "contract_id",
            unique=True,
            postgresql_where=text("is_primary = TRUE"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contracts.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[date] = mapped_column(Date)
    left_at: Mapped[date | None] = mapped_column(Date)

    contract: Mapped[Contract] = relationship(back_populates="members")
