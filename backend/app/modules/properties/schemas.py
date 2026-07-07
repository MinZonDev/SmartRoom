"""Pydantic schemas cho module properties (tòa nhà / phòng / dịch vụ / chỉ số)."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.shared.enums import RoomStatus, ServiceChargeType

# ---------------------------------------------------------------- properties


class PropertyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    address: str = Field(min_length=5, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    description: str | None = None


class PropertyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    address: str | None = Field(default=None, min_length=5, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    description: str | None = None


class PropertyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    address: str
    city: str | None
    district: str | None
    description: str | None


# --------------------------------------------------------------------- rooms


class RoomCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    floor: int | None = None
    area_m2: Decimal | None = Field(default=None, gt=0)
    base_price: Decimal = Field(ge=0)
    max_occupants: int = Field(default=1, gt=0)
    status: RoomStatus = RoomStatus.AVAILABLE


class RoomUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=30)
    floor: int | None = None
    area_m2: Decimal | None = Field(default=None, gt=0)
    base_price: Decimal | None = Field(default=None, ge=0)
    max_occupants: int | None = Field(default=None, gt=0)
    status: RoomStatus | None = None


class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    property_id: UUID
    code: str
    floor: int | None
    area_m2: Decimal | None
    base_price: Decimal
    max_occupants: int
    status: RoomStatus


# ------------------------------------------------------------------ services


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    unit: str | None = Field(default=None, max_length=20)
    unit_price: Decimal = Field(ge=0)
    charge_type: ServiceChargeType = ServiceChargeType.PER_UNIT
    is_active: bool = True


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    unit: str | None = Field(default=None, max_length=20)
    unit_price: Decimal | None = Field(default=None, ge=0)
    charge_type: ServiceChargeType | None = None
    is_active: bool | None = None


class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    property_id: UUID
    name: str
    unit: str | None
    unit_price: Decimal
    charge_type: ServiceChargeType
    is_active: bool


# ------------------------------------------------------------ meter readings


class MeterReadingUpsert(BaseModel):
    """Ghi/sửa chỉ số công tơ của một phòng theo kỳ (upsert theo service+period)."""

    service_id: UUID
    period: date
    previous_value: Decimal = Field(ge=0)
    current_value: Decimal = Field(ge=0)
    reading_date: date | None = None

    @field_validator("period")
    @classmethod
    def normalize_period(cls, v: date) -> date:
        return v.replace(day=1)

    @model_validator(mode="after")
    def check_values(self) -> "MeterReadingUpsert":
        if self.current_value < self.previous_value:
            raise ValueError("current_value phải >= previous_value")
        return self


class MeterReadingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    room_id: UUID
    service_id: UUID
    period: date
    previous_value: Decimal
    current_value: Decimal
    reading_date: date
    image_url: str | None
