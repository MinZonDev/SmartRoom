"""Integration test: số dư nhóm chia tiền tính từ dữ liệu thật trong Postgres."""

from decimal import Decimal

import pytest

from app.modules.auth.models import User
from app.modules.expenses.schemas import (
    ExpenseCreate,
    GroupCreate,
    SettlementCreate,
)
from app.modules.expenses.service import ExpenseService

pytestmark = pytest.mark.integration


async def test_balances_va_settlement_flow(db_session) -> None:
    users = [
        User(full_name=f"U{i}", email=f"u{i}@it.test", password_hash="x")
        for i in range(3)
    ]
    db_session.add_all(users)
    await db_session.commit()
    ua, ub, uc = users

    service = ExpenseService(db_session)
    group = await service.create_group(
        ua.id, GroupCreate(name="Phong IT", member_ids=[ub.id, uc.id])
    )

    # A chi 300k chia đều -> A +200k, B -100k, C -100k
    await service.create_expense(
        group.id, ua.id, ExpenseCreate(title="Dien", amount=Decimal("300000"))
    )
    balances = {
        b.user_id: b.balance for b in await service.get_balances(group.id, ua.id)
    }
    assert balances[ua.id] == Decimal("200000.00")
    assert balances[ub.id] == Decimal("-100000.00")
    assert balances[uc.id] == Decimal("-100000.00")

    # Tổng số dư cả nhóm luôn = 0 (bất biến kế toán)
    assert sum(balances.values()) == Decimal("0")

    # Gợi ý: 2 giao dịch tối thiểu, đều trả về A
    suggestions = await service.suggest_settlements(group.id, ua.id)
    assert len(suggestions) == 2
    assert all(s.to_user_id == ua.id for s in suggestions)

    # B trả A 100k: pending chưa đổi số dư -> A confirm -> B về 0
    settlement = await service.create_settlement(
        group.id, ub.id, SettlementCreate(to_user_id=ua.id, amount=Decimal("100000"))
    )
    balances = {
        b.user_id: b.balance for b in await service.get_balances(group.id, ub.id)
    }
    assert balances[ub.id] == Decimal("-100000.00")  # pending chưa tính

    await service.confirm_settlement(group.id, settlement.id, ua.id)
    balances = {
        b.user_id: b.balance for b in await service.get_balances(group.id, ub.id)
    }
    assert balances[ub.id] == Decimal("0.00")
    assert balances[ua.id] == Decimal("100000.00")
    assert sum(balances.values()) == Decimal("0")
