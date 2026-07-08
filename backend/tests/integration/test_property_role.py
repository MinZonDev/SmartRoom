"""Integration test: tạo property đầu tiên -> tự cấp role landlord."""

import pytest
from sqlalchemy import select

from app.modules.auth.models import User, UserRoleAssignment
from app.modules.properties.schemas import PropertyCreate
from app.modules.properties.service import PropertyService
from app.shared.enums import UserRole

pytestmark = pytest.mark.integration


async def test_tao_property_cap_role_landlord_idempotent(db_session) -> None:
    user = User(full_name="Chu Moi", email="chumoi@it.test", password_hash="x")
    db_session.add(user)
    await db_session.commit()

    service = PropertyService(db_session)
    await service.create_property(
        user.id, PropertyCreate(name="Nha 1", address="1 Test St")
    )

    roles = (
        await db_session.scalars(
            select(UserRoleAssignment).where(UserRoleAssignment.user_id == user.id)
        )
    ).all()
    assert len(roles) == 1
    assert roles[0].role == UserRole.LANDLORD

    # Tạo property thứ 2 -> không duplicate role (on_conflict_do_nothing)
    await service.create_property(
        user.id, PropertyCreate(name="Nha 2", address="2 Test St")
    )
    roles = (
        await db_session.scalars(
            select(UserRoleAssignment).where(UserRoleAssignment.user_id == user.id)
        )
    ).all()
    assert len(roles) == 1
