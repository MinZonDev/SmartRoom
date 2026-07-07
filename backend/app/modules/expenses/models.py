"""ORM models: expense_groups, expense_group_members, expenses, expense_shares, settlements."""

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
from app.modules.auth.models import User
from app.shared.enums import SettlementStatus, SplitMethod


class ExpenseGroup(Base):
    __tablename__ = "expense_groups"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    room_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rooms.id"))
    name: Mapped[str] = mapped_column(String(120))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )

    members: Mapped[list["ExpenseGroupMember"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class ExpenseGroupMember(Base):
    __tablename__ = "expense_group_members"

    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("expense_groups.id"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), primary_key=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    left_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    group: Mapped[ExpenseGroup] = relationship(back_populates="members")
    user: Mapped[User] = relationship()


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("expense_groups.id"))
    payer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(150))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    expense_date: Mapped[date] = mapped_column(Date)
    split_method: Mapped[SplitMethod] = mapped_column(
        SAEnum(
            SplitMethod,
            name="split_method",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=SplitMethod.EQUAL,
    )
    receipt_image_url: Mapped[str | None]
    note: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )

    shares: Mapped[list["ExpenseShare"]] = relationship(
        back_populates="expense", cascade="all, delete-orphan"
    )


class ExpenseShare(Base):
    __tablename__ = "expense_shares"
    __table_args__ = (UniqueConstraint("expense_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    expense_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("expenses.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    share_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    expense: Mapped[Expense] = relationship(back_populates="shares")


class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("expense_groups.id"))
    from_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    to_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    status: Mapped[SettlementStatus] = mapped_column(
        SAEnum(
            SettlementStatus,
            name="settlement_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=SettlementStatus.PENDING,
    )
    settled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
