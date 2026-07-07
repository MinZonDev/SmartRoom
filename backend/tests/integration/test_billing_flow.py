"""Integration test: InvoiceGenerationService với Postgres thật.

Kịch bản khớp nghiệp vụ: phòng 3tr, điện per_unit, nước per_person (x2 người),
internet per_room, rác flat -> tổng phải đúng từng đồng.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.modules.auth.models import User
from app.modules.billing.models import Invoice
from app.modules.billing.service import InvoiceGenerationService
from app.modules.contracts.models import Contract, ContractMember
from app.modules.properties.models import (
    MeterReading,
    Property,
    Room,
    UtilityService,
)
from app.shared.enums import ContractStatus, RoomStatus, ServiceChargeType
from tests.integration.conftest import FakeStorage

pytestmark = pytest.mark.integration

PERIOD = date(2026, 7, 1)


async def _seed_property(session, *, with_reading: bool = True) -> Property:
    landlord = User(
        full_name="Chu Nha", email="chunha@it.test", password_hash="x"
    )
    tenant_a = User(full_name="Tenant A", email="a@it.test", password_hash="x")
    tenant_b = User(full_name="Tenant B", email="b@it.test", password_hash="x")
    session.add_all([landlord, tenant_a, tenant_b])
    await session.flush()

    prop = Property(owner_id=landlord.id, name="Nha Test", address="1 Test St")
    session.add(prop)
    await session.flush()

    room = Room(
        property_id=prop.id, code="P1", base_price=Decimal("3000000"),
        max_occupants=2, status=RoomStatus.OCCUPIED,
    )
    session.add(room)

    electricity = UtilityService(
        property_id=prop.id, name="Dien", unit="kWh",
        unit_price=Decimal("3500"), charge_type=ServiceChargeType.PER_UNIT,
    )
    water = UtilityService(
        property_id=prop.id, name="Nuoc", unit="nguoi",
        unit_price=Decimal("100000"), charge_type=ServiceChargeType.PER_PERSON,
    )
    internet = UtilityService(
        property_id=prop.id, name="Internet",
        unit_price=Decimal("150000"), charge_type=ServiceChargeType.PER_ROOM,
    )
    trash = UtilityService(
        property_id=prop.id, name="Rac",
        unit_price=Decimal("30000"), charge_type=ServiceChargeType.FLAT,
    )
    session.add_all([electricity, water, internet, trash])
    await session.flush()

    contract = Contract(
        room_id=room.id, code="HD-IT-01", monthly_rent=Decimal("3000000"),
        start_date=date(2026, 1, 1), status=ContractStatus.ACTIVE,
        members=[
            ContractMember(user_id=tenant_a.id, is_primary=True, joined_at=date(2026, 1, 1)),
            ContractMember(user_id=tenant_b.id, is_primary=False, joined_at=date(2026, 2, 1)),
        ],
    )
    session.add(contract)

    if with_reading:
        session.add(
            MeterReading(
                room_id=room.id, service_id=electricity.id, period=PERIOD,
                previous_value=Decimal("100"), current_value=Decimal("180"),
                reading_date=PERIOD,
            )
        )
    await session.commit()
    return prop


async def test_tao_hoa_don_dung_tung_dong(db_session) -> None:
    prop = await _seed_property(db_session)
    storage = FakeStorage()
    summary = await InvoiceGenerationService(db_session, storage).generate_for_property(
        prop.id, PERIOD
    )

    assert summary.invoices_created == 1
    assert summary.errors == []

    invoice = (await db_session.scalars(select(Invoice))).one()
    # 3tr phòng + 80kWh*3.5k + nước 2 người*100k + internet 150k + rác 30k
    assert invoice.total_amount == Decimal("3660000.00")
    assert invoice.pdf_url is not None
    assert len(storage.uploaded) == 1

    amounts = sorted(item.amount for item in invoice.items)
    assert amounts == [
        Decimal("30000.00"),      # rác flat
        Decimal("150000.00"),     # internet per_room
        Decimal("200000.00"),     # nước per_person x2
        Decimal("280000.00"),     # điện 80 kWh
        Decimal("3000000.00"),    # tiền phòng
    ]


async def test_idempotent_chay_lai_khong_tao_trung(db_session) -> None:
    prop = await _seed_property(db_session)
    service = InvoiceGenerationService(db_session, FakeStorage())
    await service.generate_for_property(prop.id, PERIOD)

    summary2 = await service.generate_for_property(prop.id, PERIOD)
    assert summary2.invoices_created == 0
    assert len(summary2.skipped) == 1

    count = len((await db_session.scalars(select(Invoice))).all())
    assert count == 1


async def test_thieu_chi_so_ghi_loi_khong_tao_hoa_don(db_session) -> None:
    prop = await _seed_property(db_session, with_reading=False)
    summary = await InvoiceGenerationService(
        db_session, FakeStorage()
    ).generate_for_property(prop.id, PERIOD)

    assert summary.invoices_created == 0
    assert len(summary.errors) == 1
    assert "Dien" in summary.errors[0]
