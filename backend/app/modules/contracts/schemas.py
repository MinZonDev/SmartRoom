"""Pydantic schemas cho module contracts."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.shared.enums import ContractStatus


class ContractMemberCreate(BaseModel):
    user_id: UUID
    is_primary: bool = False
    joined_at: date | None = None


class ContractCreate(BaseModel):
    room_id: UUID
    code: str | None = Field(
        default=None, max_length=30, description="Bỏ trống để hệ thống tự sinh"
    )
    deposit_amount: Decimal = Field(default=Decimal("0"), ge=0)
    monthly_rent: Decimal = Field(ge=0)
    billing_day: int = Field(default=1, ge=1, le=28)
    start_date: date
    end_date: date | None = None
    note: str | None = None
    members: list[ContractMemberCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_business_rules(self) -> "ContractCreate":
        if self.end_date is not None and self.end_date <= self.start_date:
            raise ValueError("end_date phải sau start_date")
        primaries = sum(1 for m in self.members if m.is_primary)
        if primaries != 1:
            raise ValueError("Phải có đúng 1 thành viên đại diện (is_primary=true)")
        user_ids = [m.user_id for m in self.members]
        if len(user_ids) != len(set(user_ids)):
            raise ValueError("Thành viên bị trùng user_id")
        return self


class ContractUpdate(BaseModel):
    """Chỉ sửa được điều khoản khi hợp đồng còn pending (service enforce)."""

    deposit_amount: Decimal | None = Field(default=None, ge=0)
    monthly_rent: Decimal | None = Field(default=None, ge=0)
    billing_day: int | None = Field(default=None, ge=1, le=28)
    start_date: date | None = None
    end_date: date | None = None
    note: str | None = None


class ContractMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    is_primary: bool
    joined_at: date
    left_at: date | None


class ContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    room_id: UUID
    code: str
    deposit_amount: Decimal
    monthly_rent: Decimal
    billing_day: int
    start_date: date
    end_date: date | None
    status: ContractStatus
    note: str | None
    members: list[ContractMemberResponse]


class AddMemberRequest(BaseModel):
    user_id: UUID
    joined_at: date | None = None
