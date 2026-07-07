"""HTTP layer module expenses."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user_id
from app.modules.expenses.schemas import (
    AddGroupMemberRequest,
    BalanceEntry,
    ExpenseCreate,
    ExpenseResponse,
    GroupCreate,
    GroupResponse,
    SettlementCreate,
    SettlementResponse,
    SettlementSuggestion,
)
from app.modules.expenses.service import ExpenseService

router = APIRouter(prefix="/expense-groups", tags=["expenses"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserIdDep = Annotated[UUID, Depends(get_current_user_id)]


def _service(session: SessionDep) -> ExpenseService:
    return ExpenseService(session)


ServiceDep = Annotated[ExpenseService, Depends(_service)]

# -------------------------------------------------------------------- groups


@router.post("", status_code=status.HTTP_201_CREATED, response_model=GroupResponse)
async def create_group(
    payload: GroupCreate, user_id: UserIdDep, service: ServiceDep
) -> GroupResponse:
    return GroupResponse.model_validate(await service.create_group(user_id, payload))


@router.get("", response_model=list[GroupResponse])
async def list_my_groups(
    user_id: UserIdDep, service: ServiceDep
) -> list[GroupResponse]:
    groups = await service.list_my_groups(user_id)
    return [GroupResponse.model_validate(g) for g in groups]


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: UUID, user_id: UserIdDep, service: ServiceDep
) -> GroupResponse:
    return GroupResponse.model_validate(await service.get_group(group_id, user_id))


@router.post("/{group_id}/members", response_model=GroupResponse)
async def add_group_member(
    group_id: UUID,
    payload: AddGroupMemberRequest,
    user_id: UserIdDep,
    service: ServiceDep,
) -> GroupResponse:
    return GroupResponse.model_validate(
        await service.add_member(group_id, user_id, payload)
    )


# ------------------------------------------------------------------ expenses


@router.post(
    "/{group_id}/expenses",
    status_code=status.HTTP_201_CREATED,
    response_model=ExpenseResponse,
    summary="Ghi khoản chi (chia equal / ratio / exact)",
)
async def create_expense(
    group_id: UUID, payload: ExpenseCreate, user_id: UserIdDep, service: ServiceDep
) -> ExpenseResponse:
    return ExpenseResponse.model_validate(
        await service.create_expense(group_id, user_id, payload)
    )


@router.get("/{group_id}/expenses", response_model=list[ExpenseResponse])
async def list_expenses(
    group_id: UUID, user_id: UserIdDep, service: ServiceDep
) -> list[ExpenseResponse]:
    expenses = await service.list_expenses(group_id, user_id)
    return [ExpenseResponse.model_validate(e) for e in expenses]


@router.delete(
    "/{group_id}/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_expense(
    group_id: UUID, expense_id: UUID, user_id: UserIdDep, service: ServiceDep
) -> None:
    await service.delete_expense(group_id, expense_id, user_id)


# ---------------------------------------------------- balances & settlements


@router.get(
    "/{group_id}/balances",
    response_model=list[BalanceEntry],
    summary="Số dư từng thành viên (dương = được nhận, âm = đang nợ)",
)
async def get_balances(
    group_id: UUID, user_id: UserIdDep, service: ServiceDep
) -> list[BalanceEntry]:
    return await service.get_balances(group_id, user_id)


@router.get(
    "/{group_id}/settlement-suggestions",
    response_model=list[SettlementSuggestion],
    summary="Gợi ý trả nợ tối ưu (số giao dịch tối thiểu)",
)
async def suggest_settlements(
    group_id: UUID, user_id: UserIdDep, service: ServiceDep
) -> list[SettlementSuggestion]:
    return await service.suggest_settlements(group_id, user_id)


@router.post(
    "/{group_id}/settlements",
    status_code=status.HTTP_201_CREATED,
    response_model=SettlementResponse,
    summary="Ghi nhận đã trả nợ (pending — chờ người nhận xác nhận)",
)
async def create_settlement(
    group_id: UUID, payload: SettlementCreate, user_id: UserIdDep, service: ServiceDep
) -> SettlementResponse:
    return SettlementResponse.model_validate(
        await service.create_settlement(group_id, user_id, payload)
    )


@router.get("/{group_id}/settlements", response_model=list[SettlementResponse])
async def list_settlements(
    group_id: UUID, user_id: UserIdDep, service: ServiceDep
) -> list[SettlementResponse]:
    settlements = await service.list_settlements(group_id, user_id)
    return [SettlementResponse.model_validate(s) for s in settlements]


@router.post(
    "/{group_id}/settlements/{settlement_id}/confirm",
    response_model=SettlementResponse,
    summary="Người nhận xác nhận đã nhận tiền",
)
async def confirm_settlement(
    group_id: UUID, settlement_id: UUID, user_id: UserIdDep, service: ServiceDep
) -> SettlementResponse:
    return SettlementResponse.model_validate(
        await service.confirm_settlement(group_id, settlement_id, user_id)
    )


@router.post(
    "/{group_id}/settlements/{settlement_id}/cancel",
    response_model=SettlementResponse,
)
async def cancel_settlement(
    group_id: UUID, settlement_id: UUID, user_id: UserIdDep, service: ServiceDep
) -> SettlementResponse:
    return SettlementResponse.model_validate(
        await service.cancel_settlement(group_id, settlement_id, user_id)
    )
