"""HTTP layer module contracts."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user_id
from app.modules.contracts.schemas import (
    AddMemberRequest,
    ContractCreate,
    ContractResponse,
    ContractUpdate,
)
from app.modules.contracts.service import ContractService
from app.shared.enums import ContractStatus

router = APIRouter(prefix="/contracts", tags=["contracts"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserIdDep = Annotated[UUID, Depends(get_current_user_id)]


def _service(session: SessionDep) -> ContractService:
    return ContractService(session)


ServiceDep = Annotated[ContractService, Depends(_service)]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ContractResponse,
    summary="Tạo hợp đồng (trạng thái pending)",
)
async def create_contract(
    payload: ContractCreate, user_id: UserIdDep, service: ServiceDep
) -> ContractResponse:
    return ContractResponse.model_validate(
        await service.create_contract(user_id, payload)
    )


@router.get("", response_model=list[ContractResponse])
async def list_contracts(
    user_id: UserIdDep,
    service: ServiceDep,
    property_id: UUID | None = None,
    room_id: UUID | None = None,
    status_filter: ContractStatus | None = None,
) -> list[ContractResponse]:
    contracts = await service.list_contracts(
        user_id, property_id=property_id, room_id=room_id, status=status_filter
    )
    return [ContractResponse.model_validate(c) for c in contracts]


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: UUID, user_id: UserIdDep, service: ServiceDep
) -> ContractResponse:
    return ContractResponse.model_validate(
        await service.get_contract(contract_id, user_id)
    )


@router.patch(
    "/{contract_id}",
    response_model=ContractResponse,
    summary="Sửa điều khoản (chỉ khi pending)",
)
async def update_contract(
    contract_id: UUID,
    payload: ContractUpdate,
    user_id: UserIdDep,
    service: ServiceDep,
) -> ContractResponse:
    return ContractResponse.model_validate(
        await service.update_contract(contract_id, user_id, payload)
    )


@router.post(
    "/{contract_id}/activate",
    response_model=ContractResponse,
    summary="Kích hoạt hợp đồng (phòng chuyển sang occupied)",
)
async def activate_contract(
    contract_id: UUID, user_id: UserIdDep, service: ServiceDep
) -> ContractResponse:
    return ContractResponse.model_validate(
        await service.activate(contract_id, user_id)
    )


@router.post(
    "/{contract_id}/terminate",
    response_model=ContractResponse,
    summary="Chấm dứt hợp đồng (phòng trả về available)",
)
async def terminate_contract(
    contract_id: UUID, user_id: UserIdDep, service: ServiceDep
) -> ContractResponse:
    return ContractResponse.model_validate(
        await service.terminate(contract_id, user_id)
    )


@router.post(
    "/{contract_id}/members",
    response_model=ContractResponse,
    summary="Thêm người ở ghép vào hợp đồng",
)
async def add_member(
    contract_id: UUID,
    payload: AddMemberRequest,
    user_id: UserIdDep,
    service: ServiceDep,
) -> ContractResponse:
    return ContractResponse.model_validate(
        await service.add_member(contract_id, user_id, payload)
    )


@router.delete(
    "/{contract_id}/members/{member_user_id}",
    response_model=ContractResponse,
    summary="Thành viên rời phòng (set left_at, giữ lịch sử)",
)
async def remove_member(
    contract_id: UUID,
    member_user_id: UUID,
    user_id: UserIdDep,
    service: ServiceDep,
) -> ContractResponse:
    return ContractResponse.model_validate(
        await service.remove_member(contract_id, user_id, member_user_id)
    )
