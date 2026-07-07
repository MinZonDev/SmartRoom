"""HTTP layer module properties — router mỏng, mọi logic ở PropertyService."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user_id
from app.modules.properties.schemas import (
    MeterReadingResponse,
    MeterReadingUpsert,
    PropertyCreate,
    PropertyResponse,
    PropertyUpdate,
    RoomCreate,
    RoomResponse,
    RoomUpdate,
    ServiceCreate,
    ServiceResponse,
    ServiceUpdate,
)
from app.modules.properties.service import PropertyService

router = APIRouter(tags=["properties"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserIdDep = Annotated[UUID, Depends(get_current_user_id)]


def _service(session: SessionDep) -> PropertyService:
    return PropertyService(session)


ServiceDep = Annotated[PropertyService, Depends(_service)]

# ---------------------------------------------------------------- properties


@router.post(
    "/properties", status_code=status.HTTP_201_CREATED, response_model=PropertyResponse
)
async def create_property(
    payload: PropertyCreate, user_id: UserIdDep, service: ServiceDep
) -> PropertyResponse:
    prop = await service.create_property(user_id, payload)
    return PropertyResponse.model_validate(prop)


@router.get("/properties", response_model=list[PropertyResponse])
async def list_my_properties(
    user_id: UserIdDep, service: ServiceDep
) -> list[PropertyResponse]:
    props = await service.list_properties(user_id)
    return [PropertyResponse.model_validate(p) for p in props]


@router.get("/properties/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: UUID, user_id: UserIdDep, service: ServiceDep
) -> PropertyResponse:
    return PropertyResponse.model_validate(
        await service.get_property(property_id, user_id)
    )


@router.patch("/properties/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: UUID,
    payload: PropertyUpdate,
    user_id: UserIdDep,
    service: ServiceDep,
) -> PropertyResponse:
    return PropertyResponse.model_validate(
        await service.update_property(property_id, user_id, payload)
    )


@router.delete("/properties/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(
    property_id: UUID, user_id: UserIdDep, service: ServiceDep
) -> None:
    await service.delete_property(property_id, user_id)


# --------------------------------------------------------------------- rooms


@router.post(
    "/properties/{property_id}/rooms",
    status_code=status.HTTP_201_CREATED,
    response_model=RoomResponse,
)
async def create_room(
    property_id: UUID, payload: RoomCreate, user_id: UserIdDep, service: ServiceDep
) -> RoomResponse:
    return RoomResponse.model_validate(
        await service.create_room(property_id, user_id, payload)
    )


@router.get("/properties/{property_id}/rooms", response_model=list[RoomResponse])
async def list_rooms(
    property_id: UUID, user_id: UserIdDep, service: ServiceDep
) -> list[RoomResponse]:
    rooms = await service.list_rooms(property_id, user_id)
    return [RoomResponse.model_validate(r) for r in rooms]


@router.patch("/rooms/{room_id}", response_model=RoomResponse)
async def update_room(
    room_id: UUID, payload: RoomUpdate, user_id: UserIdDep, service: ServiceDep
) -> RoomResponse:
    return RoomResponse.model_validate(
        await service.update_room(room_id, user_id, payload)
    )


@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    room_id: UUID, user_id: UserIdDep, service: ServiceDep
) -> None:
    await service.delete_room(room_id, user_id)


# ------------------------------------------------------------------ services


@router.post(
    "/properties/{property_id}/services",
    status_code=status.HTTP_201_CREATED,
    response_model=ServiceResponse,
)
async def create_utility_service(
    property_id: UUID, payload: ServiceCreate, user_id: UserIdDep, service: ServiceDep
) -> ServiceResponse:
    return ServiceResponse.model_validate(
        await service.create_service(property_id, user_id, payload)
    )


@router.get(
    "/properties/{property_id}/services", response_model=list[ServiceResponse]
)
async def list_utility_services(
    property_id: UUID, user_id: UserIdDep, service: ServiceDep
) -> list[ServiceResponse]:
    services = await service.list_services(property_id, user_id)
    return [ServiceResponse.model_validate(s) for s in services]


@router.patch("/services/{service_id}", response_model=ServiceResponse)
async def update_utility_service(
    service_id: UUID, payload: ServiceUpdate, user_id: UserIdDep, service: ServiceDep
) -> ServiceResponse:
    return ServiceResponse.model_validate(
        await service.update_service(service_id, user_id, payload)
    )


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_utility_service(
    service_id: UUID, user_id: UserIdDep, service: ServiceDep
) -> None:
    await service.delete_service(service_id, user_id)


# ------------------------------------------------------------ meter readings


@router.put(
    "/rooms/{room_id}/meter-readings",
    response_model=MeterReadingResponse,
    summary="Ghi/cập nhật chỉ số công tơ theo kỳ (upsert)",
)
async def upsert_meter_reading(
    room_id: UUID,
    payload: MeterReadingUpsert,
    user_id: UserIdDep,
    service: ServiceDep,
) -> MeterReadingResponse:
    return MeterReadingResponse.model_validate(
        await service.upsert_meter_reading(room_id, user_id, payload)
    )


@router.get(
    "/rooms/{room_id}/meter-readings", response_model=list[MeterReadingResponse]
)
async def list_meter_readings(
    room_id: UUID, user_id: UserIdDep, service: ServiceDep
) -> list[MeterReadingResponse]:
    readings = await service.list_meter_readings(room_id, user_id)
    return [MeterReadingResponse.model_validate(r) for r in readings]
