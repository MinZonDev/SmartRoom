"""Seed dữ liệu demo để test luồng 'Chốt tháng' end-to-end.

Chạy:  python -m scripts.seed_demo   (từ thư mục backend/)

Tạo: 1 chủ nhà + 2 khách thuê, 1 tòa nhà, 2 phòng, 4 dịch vụ,
2 hợp đồng active, chỉ số điện/nước kỳ 2026-07.
Idempotent: đã seed rồi thì chỉ in lại IDs.
"""

import asyncio
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.core.database import async_session_factory
from app.modules.auth.models import User
from app.modules.auth.security import hash_password
from app.modules.contracts.models import Contract, ContractMember
from app.modules.properties.models import (
    MeterReading,
    Property,
    Room,
    UtilityService,
)
from app.shared.enums import ContractStatus, RoomStatus, ServiceChargeType

PERIOD = date(2026, 7, 1)
LANDLORD_EMAIL = "chunha@smartroom.demo"
DEMO_PASSWORD = "smartroom123"  # mật khẩu chung cho mọi user demo


async def seed() -> None:
    password_hash = hash_password(DEMO_PASSWORD)
    async with async_session_factory() as session:
        existing = await session.scalar(
            select(User).where(User.email == LANDLORD_EMAIL)
        )
        if existing is not None:
            # Đồng bộ lại hash cho dữ liệu seed cũ (trước khi có module auth)
            users = (await session.scalars(select(User))).all()
            for user in users:
                user.password_hash = password_hash
            await session.commit()
            prop = await session.scalar(
                select(Property).where(Property.owner_id == existing.id)
            )
            print("Đã seed từ trước — password đã đồng bộ. Dùng các thông tin sau:")
            print(f"  Login chủ nhà : {LANDLORD_EMAIL} / {DEMO_PASSWORD}")
            print(f"  user_id       : {existing.id}")
            print(f"  property_id   : {prop.id if prop else '?'}")
            return

        landlord = User(
            full_name="Ông Chủ Nhà",
            email=LANDLORD_EMAIL,
            phone="0900000001",
            password_hash=password_hash,
        )
        tenant_a = User(
            full_name="Khách Thuê A",
            email="tenant.a@smartroom.demo",
            phone="0900000002",
            password_hash=password_hash,
        )
        tenant_b = User(
            full_name="Khách Thuê B",
            email="tenant.b@smartroom.demo",
            phone="0900000003",
            password_hash=password_hash,
        )
        session.add_all([landlord, tenant_a, tenant_b])
        await session.flush()

        prop = Property(
            owner_id=landlord.id,
            name="Nhà trọ Bình An",
            address="123 Đường Số 1",
            city="TP.HCM",
            district="Thủ Đức",
        )
        session.add(prop)
        await session.flush()

        room_101 = Room(
            property_id=prop.id, code="P101", floor=1,
            area_m2=Decimal("20"), base_price=Decimal("3500000"),
            max_occupants=2, status=RoomStatus.OCCUPIED,
        )
        room_102 = Room(
            property_id=prop.id, code="P102", floor=1,
            area_m2=Decimal("25"), base_price=Decimal("4200000"),
            max_occupants=2, status=RoomStatus.OCCUPIED,
        )
        session.add_all([room_101, room_102])

        electricity = UtilityService(
            property_id=prop.id, name="Dien", unit="kWh",
            unit_price=Decimal("3500"), charge_type=ServiceChargeType.PER_UNIT,
        )
        water = UtilityService(
            property_id=prop.id, name="Nuoc", unit="nguoi",
            unit_price=Decimal("100000"), charge_type=ServiceChargeType.PER_PERSON,
        )
        internet = UtilityService(
            property_id=prop.id, name="Internet", unit="thang",
            unit_price=Decimal("150000"), charge_type=ServiceChargeType.PER_ROOM,
        )
        trash = UtilityService(
            property_id=prop.id, name="Rac", unit="thang",
            unit_price=Decimal("30000"), charge_type=ServiceChargeType.FLAT,
        )
        session.add_all([electricity, water, internet, trash])
        await session.flush()

        contract_101 = Contract(
            room_id=room_101.id, code="HD-2026-0001",
            deposit_amount=Decimal("3500000"), monthly_rent=Decimal("3500000"),
            billing_day=1, start_date=date(2026, 1, 5),
            status=ContractStatus.ACTIVE,
        )
        contract_102 = Contract(
            room_id=room_102.id, code="HD-2026-0002",
            deposit_amount=Decimal("4200000"), monthly_rent=Decimal("4200000"),
            billing_day=1, start_date=date(2026, 3, 1),
            status=ContractStatus.ACTIVE,
        )
        session.add_all([contract_101, contract_102])
        await session.flush()

        session.add_all(
            [
                ContractMember(
                    contract_id=contract_101.id, user_id=tenant_a.id,
                    is_primary=True, joined_at=date(2026, 1, 5),
                ),
                # Phòng 102 ghép 2 người -> dịch vụ per_person tính x2
                ContractMember(
                    contract_id=contract_102.id, user_id=tenant_b.id,
                    is_primary=True, joined_at=date(2026, 3, 1),
                ),
                ContractMember(
                    contract_id=contract_102.id, user_id=tenant_a.id,
                    is_primary=False, joined_at=date(2026, 4, 1),
                ),
            ]
        )

        session.add_all(
            [
                MeterReading(
                    room_id=room_101.id, service_id=electricity.id, period=PERIOD,
                    previous_value=Decimal("1200"), current_value=Decimal("1315"),
                    reading_date=date(2026, 7, 1), created_by=landlord.id,
                ),
                MeterReading(
                    room_id=room_102.id, service_id=electricity.id, period=PERIOD,
                    previous_value=Decimal("2400"), current_value=Decimal("2562"),
                    reading_date=date(2026, 7, 1), created_by=landlord.id,
                ),
            ]
        )

        await session.commit()
        print("Seed xong! Dùng các thông tin sau để test:")
        print(f"  Login chủ nhà : {LANDLORD_EMAIL} / {DEMO_PASSWORD}")
        print(f"  user_id       : {landlord.id}")
        print(f"  property_id   : {prop.id}")
        print(f"  period        : {PERIOD.isoformat()}")
        print("\nKỳ vọng khi chốt tháng 2026-07:")
        print("  P101: phòng 3.5tr + điện 115kWh x3.5k + nước 1 người + internet + rác")
        print("  P102: phòng 4.2tr + điện 162kWh x3.5k + nước 2 người + internet + rác")


if __name__ == "__main__":
    asyncio.run(seed())
