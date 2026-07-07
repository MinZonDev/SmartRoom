"""HTTP layer module billing — router mỏng, không chứa business logic."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.core.dependencies import get_current_user_id, get_job_tracker
from app.modules.billing.schemas import (
    BillingJobStatusResponse,
    CloseMonthAccepted,
    CloseMonthRequest,
    InvoiceResponse,
)
from app.modules.billing.service import BillingCommandService, InvoiceQueryService
from app.shared.job_tracker import JobTracker
from app.shared.messaging import MessagePublisher, get_billing_publisher

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post(
    "/close-month",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CloseMonthAccepted,
    summary="Chốt tháng — sinh hóa đơn hàng loạt cho một tòa nhà (async)",
)
async def close_month(
    payload: CloseMonthRequest,
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    publisher: Annotated[MessagePublisher, Depends(get_billing_publisher)],
    tracker: Annotated[JobTracker, Depends(get_job_tracker)],
) -> CloseMonthAccepted:
    """Không block: validate xong đẩy task vào SQS và trả 202 ngay.

    Client theo dõi tiến độ qua `status_url`.
    """
    service = BillingCommandService(session, publisher, tracker)
    job_id = await service.close_month(
        property_id=payload.property_id,
        period=payload.period,
        requested_by=current_user_id,
    )
    return CloseMonthAccepted(
        job_id=job_id,
        status_url=f"{get_settings().api_v1_prefix}/billing/jobs/{job_id}",
    )


@router.get(
    "/invoices",
    response_model=list[InvoiceResponse],
    summary="Danh sách hóa đơn của một tòa nhà",
)
async def list_invoices(
    property_id: UUID,
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[InvoiceResponse]:
    invoices = await InvoiceQueryService(session).list_invoices(
        current_user_id, property_id
    )
    return [InvoiceResponse.model_validate(i) for i in invoices]


@router.get(
    "/jobs/{job_id}",
    response_model=BillingJobStatusResponse,
    summary="Trạng thái job chốt tháng",
)
async def get_job_status(
    job_id: str,
    tracker: Annotated[JobTracker, Depends(get_job_tracker)],
) -> BillingJobStatusResponse:
    data = await tracker.get(job_id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job không tồn tại hoặc đã hết hạn (TTL 24h)",
        )
    return BillingJobStatusResponse(**data)
