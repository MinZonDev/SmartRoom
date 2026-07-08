"""Business logic module properties.

Nguyên tắc authorization: mọi truy vấn đều lọc theo owner_id ngay trong SQL.
'Không tồn tại' và 'không có quyền' trả CÙNG NotFoundError — không tiết lộ
tài nguyên có tồn tại hay không cho người ngoài.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import UserRoleAssignment
from app.modules.properties.models import (
    MeterReading,
    Property,
    Room,
    UtilityService,
)
from app.modules.properties.schemas import (
    MeterReadingUpsert,
    PropertyCreate,
    PropertyUpdate,
    RoomCreate,
    RoomUpdate,
    ServiceCreate,
    ServiceUpdate,
)
from app.shared.enums import UserRole
from app.shared.exceptions import ConflictError, NotFoundError


async def get_owned_property(
    session: AsyncSession, property_id: UUID, owner_id: UUID
) -> Property:
    """Helper dùng chung (contracts service cũng import) — lọc owner ngay trong SQL."""
    prop = await session.scalar(
        select(Property).where(
            Property.id == property_id, Property.owner_id == owner_id
        )
    )
    if prop is None:
        raise NotFoundError("Tòa nhà không tồn tại hoặc bạn không có quyền")
    return prop


async def get_owned_room(
    session: AsyncSession, room_id: UUID, owner_id: UUID
) -> Room:
    room = await session.scalar(
        select(Room)
        .join(Property, Room.property_id == Property.id)
        .where(Room.id == room_id, Property.owner_id == owner_id)
    )
    if room is None:
        raise NotFoundError("Phòng không tồn tại hoặc bạn không có quyền")
    return room


def _apply_patch(entity: object, patch: dict[str, object]) -> None:
    for field, value in patch.items():
        setattr(entity, field, value)


class PropertyService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------ properties

    async def create_property(
        self, owner_id: UUID, payload: PropertyCreate
    ) -> Property:
        prop = Property(owner_id=owner_id, **payload.model_dump())
        self._session.add(prop)
        # Sở hữu tòa nhà => cấp role landlord (idempotent — có rồi thì bỏ qua)
        await self._session.execute(
            pg_insert(UserRoleAssignment)
            .values(user_id=owner_id, role=UserRole.LANDLORD)
            .on_conflict_do_nothing()
        )
        await self._session.commit()
        return prop

    async def list_properties(self, owner_id: UUID) -> list[Property]:
        result = await self._session.scalars(
            select(Property).where(Property.owner_id == owner_id)
        )
        return list(result.all())

    async def get_property(self, property_id: UUID, owner_id: UUID) -> Property:
        return await get_owned_property(self._session, property_id, owner_id)

    async def update_property(
        self, property_id: UUID, owner_id: UUID, payload: PropertyUpdate
    ) -> Property:
        prop = await get_owned_property(self._session, property_id, owner_id)
        _apply_patch(prop, payload.model_dump(exclude_unset=True))
        await self._session.commit()
        return prop

    async def delete_property(self, property_id: UUID, owner_id: UUID) -> None:
        """Xóa tòa nhà (cascade xóa phòng/dịch vụ). Còn hợp đồng -> FK RESTRICT -> 409."""
        prop = await get_owned_property(self._session, property_id, owner_id)
        await self._session.delete(prop)
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise ConflictError(
                "Không thể xóa: tòa nhà còn hợp đồng/hóa đơn tham chiếu"
            ) from None

    # ----------------------------------------------------------------- rooms

    async def create_room(
        self, property_id: UUID, owner_id: UUID, payload: RoomCreate
    ) -> Room:
        await get_owned_property(self._session, property_id, owner_id)
        room = Room(property_id=property_id, **payload.model_dump())
        self._session.add(room)
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise ConflictError(
                f"Mã phòng '{payload.code}' đã tồn tại trong tòa nhà"
            ) from None
        return room

    async def list_rooms(self, property_id: UUID, owner_id: UUID) -> list[Room]:
        await get_owned_property(self._session, property_id, owner_id)
        result = await self._session.scalars(
            select(Room).where(Room.property_id == property_id).order_by(Room.code)
        )
        return list(result.all())

    async def update_room(
        self, room_id: UUID, owner_id: UUID, payload: RoomUpdate
    ) -> Room:
        room = await get_owned_room(self._session, room_id, owner_id)
        _apply_patch(room, payload.model_dump(exclude_unset=True))
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise ConflictError("Mã phòng đã tồn tại trong tòa nhà") from None
        return room

    async def delete_room(self, room_id: UUID, owner_id: UUID) -> None:
        room = await get_owned_room(self._session, room_id, owner_id)
        await self._session.delete(room)
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise ConflictError(
                "Không thể xóa: phòng còn hợp đồng tham chiếu"
            ) from None

    # -------------------------------------------------------------- services

    async def create_service(
        self, property_id: UUID, owner_id: UUID, payload: ServiceCreate
    ) -> UtilityService:
        await get_owned_property(self._session, property_id, owner_id)
        service = UtilityService(property_id=property_id, **payload.model_dump())
        self._session.add(service)
        await self._session.commit()
        return service

    async def list_services(
        self, property_id: UUID, owner_id: UUID
    ) -> list[UtilityService]:
        await get_owned_property(self._session, property_id, owner_id)
        result = await self._session.scalars(
            select(UtilityService).where(UtilityService.property_id == property_id)
        )
        return list(result.all())

    async def update_service(
        self, service_id: UUID, owner_id: UUID, payload: ServiceUpdate
    ) -> UtilityService:
        service = await self._get_owned_service(service_id, owner_id)
        _apply_patch(service, payload.model_dump(exclude_unset=True))
        await self._session.commit()
        return service

    async def delete_service(self, service_id: UUID, owner_id: UUID) -> None:
        """Khuyến nghị dùng PATCH is_active=false thay vì xóa (giữ lịch sử hóa đơn).

        Xóa cứng chỉ được khi chưa có meter_readings/invoice_items tham chiếu.
        """
        service = await self._get_owned_service(service_id, owner_id)
        await self._session.delete(service)
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise ConflictError(
                "Không thể xóa: dịch vụ đã có chỉ số/hóa đơn — hãy tắt is_active"
            ) from None

    async def _get_owned_service(
        self, service_id: UUID, owner_id: UUID
    ) -> UtilityService:
        service = await self._session.scalar(
            select(UtilityService)
            .join(Property, UtilityService.property_id == Property.id)
            .where(UtilityService.id == service_id, Property.owner_id == owner_id)
        )
        if service is None:
            raise NotFoundError("Dịch vụ không tồn tại hoặc bạn không có quyền")
        return service

    # -------------------------------------------------------- meter readings

    async def upsert_meter_reading(
        self, room_id: UUID, owner_id: UUID, payload: MeterReadingUpsert
    ) -> MeterReading:
        """Ghi chỉ số theo (room, service, period) — có rồi thì cập nhật giá trị."""
        room = await get_owned_room(self._session, room_id, owner_id)

        service = await self._session.get(UtilityService, payload.service_id)
        if service is None or service.property_id != room.property_id:
            raise NotFoundError("Dịch vụ không thuộc tòa nhà của phòng này")

        reading = await self._session.scalar(
            select(MeterReading).where(
                MeterReading.room_id == room_id,
                MeterReading.service_id == payload.service_id,
                MeterReading.period == payload.period,
            )
        )
        # exclude_none: không gửi image_url thì giữ nguyên ảnh cũ khi update
        data = payload.model_dump(exclude={"reading_date"}, exclude_none=True)
        if reading is None:
            reading = MeterReading(
                room_id=room_id,
                created_by=owner_id,
                reading_date=payload.reading_date or payload.period,
                **data,
            )
            self._session.add(reading)
        else:
            _apply_patch(reading, data)
            if payload.reading_date is not None:
                reading.reading_date = payload.reading_date
        await self._session.commit()
        return reading

    async def list_meter_readings(
        self, room_id: UUID, owner_id: UUID
    ) -> list[MeterReading]:
        await get_owned_room(self._session, room_id, owner_id)
        result = await self._session.scalars(
            select(MeterReading)
            .where(MeterReading.room_id == room_id)
            .order_by(MeterReading.period.desc())
        )
        return list(result.all())
