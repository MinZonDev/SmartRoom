"""Pydantic schemas cho module expenses (chia tiền chi tiêu)."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.shared.enums import SettlementStatus, SplitMethod

# -------------------------------------------------------------------- groups


class GroupCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    member_ids: list[UUID] = Field(
        default_factory=list,
        description="Thành viên ban đầu (người tạo tự động là thành viên)",
    )


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str


class GroupMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: UserBrief
    joined_at: datetime
    left_at: datetime | None


class GroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_by: UUID
    created_at: datetime
    members: list[GroupMemberResponse]


class AddGroupMemberRequest(BaseModel):
    user_id: UUID


# ------------------------------------------------------------------ expenses


class ParticipantInput(BaseModel):
    user_id: UUID
    weight: Decimal | None = Field(default=None, gt=0, description="Dùng cho ratio")
    amount: Decimal | None = Field(default=None, ge=0, description="Dùng cho exact")


class ExpenseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    amount: Decimal = Field(gt=0)
    expense_date: date | None = None
    split_method: SplitMethod = SplitMethod.EQUAL
    payer_id: UUID | None = Field(
        default=None, description="Bỏ trống = người gọi API là người trả"
    )
    participants: list[ParticipantInput] | None = Field(
        default=None,
        description="equal: bỏ trống = chia đều mọi thành viên đang ở; "
        "ratio: bắt buộc kèm weight; exact: bắt buộc kèm amount",
    )
    receipt_image_url: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def validate_split(self) -> "ExpenseCreate":
        p = self.participants
        if p is not None:
            ids = [x.user_id for x in p]
            if len(ids) != len(set(ids)):
                raise ValueError("participants trùng user_id")
            if len(p) == 0:
                raise ValueError("participants không được rỗng")

        if self.split_method == SplitMethod.RATIO:
            if not p or any(x.weight is None for x in p):
                raise ValueError("ratio: mọi participant phải có weight")
        elif self.split_method == SplitMethod.EXACT:
            if not p or any(x.amount is None for x in p):
                raise ValueError("exact: mọi participant phải có amount")
            total = sum(x.amount for x in p if x.amount is not None)
            if total != self.amount:
                raise ValueError(
                    f"exact: tổng shares ({total}) phải bằng amount ({self.amount})"
                )
        return self


class ShareResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    share_amount: Decimal


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    group_id: UUID
    payer_id: UUID
    title: str
    amount: Decimal
    expense_date: date
    split_method: SplitMethod
    receipt_image_url: str | None
    note: str | None
    created_at: datetime
    shares: list[ShareResponse]


# ---------------------------------------------------- balances & settlements


class BalanceEntry(BaseModel):
    user_id: UUID
    full_name: str
    balance: Decimal = Field(
        description="Dương = được nhận lại tiền, âm = đang nợ nhóm"
    )


class SettlementSuggestion(BaseModel):
    from_user_id: UUID
    from_name: str
    to_user_id: UUID
    to_name: str
    amount: Decimal


class SettlementCreate(BaseModel):
    to_user_id: UUID
    amount: Decimal = Field(gt=0)


class SettlementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    group_id: UUID
    from_user_id: UUID
    to_user_id: UUID
    amount: Decimal
    status: SettlementStatus
    settled_at: datetime | None
    created_at: datetime
