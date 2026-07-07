"""Integration test: state machine hợp đồng + ràng buộc DB thật."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.modules.auth.models import User
from app.modules.contracts.models import Contract, ContractMember
from app.modules.contracts.service import ContractService
from app.modules.properties.models import Property, Room
from app.shared.enums import ContractStatus, RoomStatus
from app.shared.exceptions import ConflictError

pytestmark = pytest.mark.integration


async def _seed(session):
    landlord = User(full_name="Chu", email="chu@it.test", password_hash="x")
    tenant = User(full_name="Khach", email="khach@it.test", password_hash="x")
    session.add_all([landlord, tenant])
    await session.flush()
    prop = Property(owner_id=landlord.id, name="N", address="1 Test St")
    session.add(prop)
    await session.flush()
    room = Room(property_id=prop.id, code="P1", base_price=Decimal("1000000"))
    session.add(room)
    await session.flush()

    def make_contract(code: str) -> Contract:
        return Contract(
            room_id=room.id, code=code, monthly_rent=Decimal("1000000"),
            start_date=date(2026, 1, 1), status=ContractStatus.PENDING,
            members=[
                ContractMember(
                    user_id=tenant.id, is_primary=True, joined_at=date(2026, 1, 1)
                )
            ],
        )

    c1, c2 = make_contract("HD-1"), make_contract("HD-2")
    session.add_all([c1, c2])
    await session.commit()
    return landlord, room, c1, c2


async def test_activate_terminate_vong_doi_day_du(db_session) -> None:
    landlord, room, c1, c2 = await _seed(db_session)
    service = ContractService(db_session)

    activated = await service.activate(c1.id, landlord.id)
    assert activated.status == ContractStatus.ACTIVE
    assert activated.room.status == RoomStatus.OCCUPIED

    # Phòng đang có hợp đồng active -> hợp đồng 2 không kích hoạt được
    with pytest.raises(ConflictError):
        await service.activate(c2.id, landlord.id)

    terminated = await service.terminate(c1.id, landlord.id)
    assert terminated.status == ContractStatus.TERMINATED
    assert terminated.end_date is not None
    assert all(m.left_at is not None for m in terminated.members)
    assert terminated.room.status == RoomStatus.AVAILABLE

    # Phòng đã trả -> hợp đồng 2 kích hoạt được
    activated2 = await service.activate(c2.id, landlord.id)
    assert activated2.status == ContractStatus.ACTIVE


async def test_partial_index_chan_2_active_cung_phong(db_session) -> None:
    """Bypass service, ghi thẳng DB — partial unique index phải chặn."""
    _, room, c1, c2 = await _seed(db_session)
    await db_session.execute(
        text("UPDATE contracts SET status = 'active' WHERE code = 'HD-1'")
    )
    await db_session.commit()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("UPDATE contracts SET status = 'active' WHERE code = 'HD-2'")
        )
        await db_session.commit()
    await db_session.rollback()
