"""Pydantic schemas cho module billing — bao gồm cả contract của message trên SQS."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.enums import InvoiceStatus
from app.shared.job_tracker import JobStatus


class CloseMonthRequest(BaseModel):
    """Payload khi chủ nhà nhấn 'Chốt tháng' cho một tòa nhà."""

    property_id: UUID
    period: date = Field(description="Kỳ hóa đơn — ngày bất kỳ trong tháng cần chốt")

    @field_validator("period")
    @classmethod
    def normalize_to_first_day(cls, v: date) -> date:
        """Chuẩn hóa kỳ về ngày 01 để khớp UNIQUE(contract_id, period)."""
        return v.replace(day=1)


class CloseMonthAccepted(BaseModel):
    """Trả về 202 Accepted — client poll status_url để theo dõi tiến độ."""

    job_id: str
    status: JobStatus = JobStatus.PENDING
    status_url: str


class BillingJobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    meta: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    updated_at: str | None = None


class InvoiceItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contract_id: UUID
    code: str
    period: date
    due_date: date
    total_amount: Decimal
    paid_amount: Decimal
    status: InvoiceStatus
    issued_at: datetime | None
    pdf_url: str | None
    items: list[InvoiceItemResponse]


class BillingTaskMessage(BaseModel):
    """Contract của message đẩy vào SQS queue billing.

    Đây là interface giữa API và worker — thay đổi field nào phải
    tương thích ngược (worker cũ có thể còn đang xử lý message cũ).
    """

    job_id: str
    property_id: UUID
    period: date
    requested_by: UUID
