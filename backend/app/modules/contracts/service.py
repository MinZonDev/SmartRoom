"""Business logic module contracts.

Vòng đời hợp đồng là state machine, không phải CRUD thuần:

    pending --activate--> active --terminate--> terminated
       \\--terminate--> terminated

- activate : kiểm tra phòng chưa có hợp đồng active khác, đổi phòng -> occupied.
- terminate: đóng left_at cho thành viên đang ở, trả phòng -> available.
- Ràng buộc '1 phòng 1 hợp đồng active' check ở service (trả 409 đẹp);
  partial unique index uq_contracts_one_active_per_room trong DB là chốt
  chặn cuối chống race condition.
"""

from datetime import date, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models import User
from app.modules.contracts.models import Contract, ContractMember
from app.modules.contracts.schemas import (
    AddMemberRequest,
    ContractCreate,
    ContractUpdate,
)
from app.modules.properties.models import Property, Room
from app.modules.properties.service import get_owned_room
from app.shared.enums import ContractStatus, RoomStatus
from app.shared.exceptions import ConflictError, NotFoundError


class ContractService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------ CRUD

    async def create_contract(
        self, owner_id: UUID, payload: ContractCreate
    ) -> Contract:
        """Tạo hợp đồng ở trạng thái pending (kích hoạt qua /activate)."""
        room = await get_owned_room(self._session, payload.room_id, owner_id)
        await self._ensure_users_exist([m.user_id for m in payload.members])
        if len(payload.members) > room.max_occupants:
            raise ConflictError(
                f"Phòng {room.code} tối đa {room.max_occupants} người"
            )

        contract = Contract(
            room_id=room.id,
            code=payload.code or self._generate_code(payload.start_date),
            deposit_amount=payload.deposit_amount,
            monthly_rent=payload.monthly_rent,
            billing_day=payload.billing_day,
            start_date=payload.start_date,
            end_date=payload.end_date,
            note=payload.note,
            status=ContractStatus.PENDING,
            members=[
                ContractMember(
                    user_id=m.user_id,
                    is_primary=m.is_primary,
                    joined_at=m.joined_at or payload.start_date,
                )
                for m in payload.members
            ],
        )
        self._session.add(contract)
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise ConflictError(f"Mã hợp đồng '{contract.code}' đã tồn tại") from None
        return contract

    async def list_contracts(
        self,
        owner_id: UUID,
        property_id: UUID | None = None,
        room_id: UUID | None = None,
        status: ContractStatus | None = None,
    ) -> list[Contract]:
        stmt = (
            select(Contract)
            .join(Room, Contract.room_id == Room.id)
            .join(Property, Room.property_id == Property.id)
            .where(Property.owner_id == owner_id)
            .options(selectinload(Contract.members))
            .order_by(Contract.start_date.desc())
        )
        if property_id is not None:
            stmt = stmt.where(Room.property_id == property_id)
        if room_id is not None:
            stmt = stmt.where(Contract.room_id == room_id)
        if status is not None:
            stmt = stmt.where(Contract.status == status)
        result = await self._session.scalars(stmt)
        return list(result.all())

    async def get_contract(self, contract_id: UUID, owner_id: UUID) -> Contract:
        return await self._get_owned_contract(contract_id, owner_id)

    async def update_contract(
        self, contract_id: UUID, owner_id: UUID, payload: ContractUpdate
    ) -> Contract:
        contract = await self._get_owned_contract(contract_id, owner_id)
        if contract.status != ContractStatus.PENDING:
            raise ConflictError(
                "Chỉ sửa được điều khoản khi hợp đồng còn pending "
                "(hợp đồng đang hiệu lực phải terminate rồi tạo mới)"
            )
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(contract, field, value)
        if contract.end_date is not None and contract.end_date <= contract.start_date:
            await self._session.rollback()
            raise ConflictError("end_date phải sau start_date")
        await self._session.commit()
        return contract

    # --------------------------------------------------------- state machine

    async def activate(self, contract_id: UUID, owner_id: UUID) -> Contract:
        contract = await self._get_owned_contract(contract_id, owner_id)
        if contract.status != ContractStatus.PENDING:
            raise ConflictError(f"Không thể kích hoạt hợp đồng {contract.status.value}")

        other_active = await self._session.scalar(
            select(Contract.id).where(
                Contract.room_id == contract.room_id,
                Contract.status == ContractStatus.ACTIVE,
            )
        )
        if other_active is not None:
            raise ConflictError("Phòng đang có hợp đồng hiệu lực khác")

        contract.status = ContractStatus.ACTIVE
        contract.room.status = RoomStatus.OCCUPIED
        try:
            await self._session.commit()
        except IntegrityError:
            # Partial unique index chặn race: 2 request activate cùng lúc
            await self._session.rollback()
            raise ConflictError("Phòng đang có hợp đồng hiệu lực khác") from None
        return contract

    async def terminate(self, contract_id: UUID, owner_id: UUID) -> Contract:
        contract = await self._get_owned_contract(contract_id, owner_id)
        if contract.status not in (ContractStatus.PENDING, ContractStatus.ACTIVE):
            raise ConflictError(f"Hợp đồng đã ở trạng thái {contract.status.value}")

        was_active = contract.status == ContractStatus.ACTIVE
        contract.status = ContractStatus.TERMINATED
        if contract.end_date is None:
            # CHECK (end_date > start_date): chấm dứt ngay ngày bắt đầu vẫn hợp lệ
            contract.end_date = max(
                date.today(), contract.start_date + timedelta(days=1)
            )
        for member in contract.members:
            if member.left_at is None:
                member.left_at = max(date.today(), member.joined_at)
        if was_active:
            contract.room.status = RoomStatus.AVAILABLE
        await self._session.commit()
        return contract

    # --------------------------------------------------------------- members

    async def add_member(
        self, contract_id: UUID, owner_id: UUID, payload: AddMemberRequest
    ) -> Contract:
        contract = await self._get_owned_contract(contract_id, owner_id)
        if contract.status not in (ContractStatus.PENDING, ContractStatus.ACTIVE):
            raise ConflictError("Hợp đồng đã kết thúc, không thêm được thành viên")
        await self._ensure_users_exist([payload.user_id])

        current = [m for m in contract.members if m.left_at is None]
        if len(current) >= contract.room.max_occupants:
            raise ConflictError(
                f"Phòng đã đủ {contract.room.max_occupants} người tối đa"
            )

        self._session.add(
            ContractMember(
                contract_id=contract.id,
                user_id=payload.user_id,
                is_primary=False,
                joined_at=payload.joined_at or date.today(),
            )
        )
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise ConflictError("User đã là thành viên của hợp đồng") from None
        return await self._get_owned_contract(contract_id, owner_id)

    async def remove_member(
        self, contract_id: UUID, owner_id: UUID, user_id: UUID
    ) -> Contract:
        """Set left_at (giữ lịch sử để tính tiền per_person đúng), không xóa row."""
        contract = await self._get_owned_contract(contract_id, owner_id)
        member = next(
            (
                m
                for m in contract.members
                if m.user_id == user_id and m.left_at is None
            ),
            None,
        )
        if member is None:
            raise NotFoundError("User không phải thành viên đang ở của hợp đồng")
        if member.is_primary:
            raise ConflictError(
                "Không thể rời người đại diện — hãy terminate hợp đồng"
            )
        member.left_at = max(date.today(), member.joined_at)
        await self._session.commit()
        return contract

    # --------------------------------------------------------------- helpers

    async def _get_owned_contract(
        self, contract_id: UUID, owner_id: UUID
    ) -> Contract:
        contract = await self._session.scalar(
            select(Contract)
            .join(Room, Contract.room_id == Room.id)
            .join(Property, Room.property_id == Property.id)
            .where(Contract.id == contract_id, Property.owner_id == owner_id)
            # Eager-load mọi relationship dùng sau query (tránh lỗi greenlet)
            .options(selectinload(Contract.members), selectinload(Contract.room))
        )
        if contract is None:
            raise NotFoundError("Hợp đồng không tồn tại hoặc bạn không có quyền")
        return contract

    async def _ensure_users_exist(self, user_ids: list[UUID]) -> None:
        found = (
            await self._session.scalars(select(User.id).where(User.id.in_(user_ids)))
        ).all()
        missing = set(user_ids) - set(found)
        if missing:
            raise NotFoundError(
                f"User không tồn tại: {', '.join(str(u) for u in missing)}"
            )

    @staticmethod
    def _generate_code(start_date: date) -> str:
        return f"HD-{start_date.year}-{uuid4().hex[:6].upper()}"
