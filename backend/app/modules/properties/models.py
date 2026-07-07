"""ORM models: properties, rooms, services, meter_readings."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    Enum as SAEnum,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.enums import RoomStatus, ServiceChargeType


def _pg_enum(enum_cls: type, name: str) -> SAEnum:
    """Map Python enum sang PG ENUM có sẵn trong DB (dùng value, không dùng name)."""
    return SAEnum(
        enum_cls, name=name, values_callable=lambda e: [m.value for m in e]
    )


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(150))
    address: Mapped[str] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None]

    rooms: Mapped[list["Room"]] = relationship(back_populates="property")


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("property_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"))
    code: Mapped[str] = mapped_column(String(30))
    floor: Mapped[int | None] = mapped_column(SmallInteger)
    area_m2: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    base_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    max_occupants: Mapped[int] = mapped_column(SmallInteger, default=1)
    status: Mapped[RoomStatus] = mapped_column(
        _pg_enum(RoomStatus, "room_status"), default=RoomStatus.AVAILABLE
    )

    property: Mapped[Property] = relationship(back_populates="rooms")


class UtilityService(Base):
    """Dịch vụ tính phí của tòa nhà: điện, nước, internet, rác... (bảng services)."""

    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"))
    name: Mapped[str] = mapped_column(String(100))
    unit: Mapped[str | None] = mapped_column(String(20))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    charge_type: Mapped[ServiceChargeType] = mapped_column(
        _pg_enum(ServiceChargeType, "service_charge_type"),
        default=ServiceChargeType.PER_UNIT,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MeterReading(Base):
    """Chỉ số công tơ theo kỳ — period luôn là ngày 01 của tháng."""

    __tablename__ = "meter_readings"
    __table_args__ = (UniqueConstraint("room_id", "service_id", "period"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id"))
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id"))
    period: Mapped[date] = mapped_column(Date)
    previous_value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    current_value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reading_date: Mapped[date] = mapped_column(Date)
    image_url: Mapped[str | None]
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
