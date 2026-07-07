"""Unit tests cho compute_shares — bất biến quan trọng nhất: SUM(shares) == amount."""

from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.modules.expenses.schemas import ExpenseCreate, ParticipantInput
from app.modules.expenses.service import compute_shares

U1, U2, U3 = UUID(int=1), UUID(int=2), UUID(int=3)
ALL = [U1, U2, U3]


def _sum(shares: list[tuple[UUID, Decimal]]) -> Decimal:
    return sum((amount for _, amount in shares), Decimal("0"))


class TestEqualSplit:
    def test_chia_het(self) -> None:
        payload = ExpenseCreate(title="x", amount=Decimal("300000"))
        shares = compute_shares(payload, ALL)
        assert [a for _, a in shares] == [Decimal("100000")] * 3

    def test_lam_tron_khong_lech_tong(self) -> None:
        """100000 / 3 không chia hết — người đầu nhận phần dư 0.01."""
        payload = ExpenseCreate(title="x", amount=Decimal("100000"))
        shares = compute_shares(payload, ALL)
        assert [str(a) for _, a in shares] == ["33333.34", "33333.33", "33333.33"]
        assert _sum(shares) == Decimal("100000")

    def test_participants_subset(self) -> None:
        payload = ExpenseCreate(
            title="x",
            amount=Decimal("100"),
            participants=[ParticipantInput(user_id=U1), ParticipantInput(user_id=U2)],
        )
        shares = compute_shares(payload, ALL)
        assert len(shares) == 2
        assert _sum(shares) == Decimal("100")

    def test_mot_nguoi_nhan_toan_bo(self) -> None:
        payload = ExpenseCreate(title="x", amount=Decimal("99999.99"))
        shares = compute_shares(payload, [U1])
        assert shares == [(U1, Decimal("99999.99"))]


class TestRatioSplit:
    def test_ty_le_2_1(self) -> None:
        payload = ExpenseCreate(
            title="x",
            amount=Decimal("90000"),
            split_method="ratio",
            participants=[
                ParticipantInput(user_id=U1, weight=Decimal("2")),
                ParticipantInput(user_id=U2, weight=Decimal("1")),
            ],
        )
        shares = compute_shares(payload, ALL)
        assert shares == [(U1, Decimal("60000")), (U2, Decimal("30000"))]

    def test_ty_le_lam_tron(self) -> None:
        """100 chia 1:1:1 — mỗi phần 33.33, dư 0.01 về người đầu."""
        payload = ExpenseCreate(
            title="x",
            amount=Decimal("100"),
            split_method="ratio",
            participants=[
                ParticipantInput(user_id=u, weight=Decimal("1")) for u in ALL
            ],
        )
        shares = compute_shares(payload, ALL)
        assert _sum(shares) == Decimal("100")
        assert shares[0][1] == Decimal("33.34")


class TestExactSplit:
    def test_giu_nguyen_gia_tri(self) -> None:
        payload = ExpenseCreate(
            title="x",
            amount=Decimal("150000"),
            split_method="exact",
            participants=[
                ParticipantInput(user_id=u, amount=Decimal("50000")) for u in ALL
            ],
        )
        shares = compute_shares(payload, ALL)
        assert _sum(shares) == Decimal("150000")


class TestSchemaValidation:
    def test_exact_lech_tong_bi_chan(self) -> None:
        with pytest.raises(ValidationError, match="phải bằng amount"):
            ExpenseCreate(
                title="x",
                amount=Decimal("100000"),
                split_method="exact",
                participants=[
                    ParticipantInput(user_id=U1, amount=Decimal("30000")),
                    ParticipantInput(user_id=U2, amount=Decimal("30000")),
                ],
            )

    def test_ratio_thieu_weight_bi_chan(self) -> None:
        with pytest.raises(ValidationError, match="weight"):
            ExpenseCreate(
                title="x",
                amount=Decimal("100"),
                split_method="ratio",
                participants=[ParticipantInput(user_id=U1)],
            )

    def test_trung_user_bi_chan(self) -> None:
        with pytest.raises(ValidationError, match="trùng"):
            ExpenseCreate(
                title="x",
                amount=Decimal("100"),
                participants=[
                    ParticipantInput(user_id=U1),
                    ParticipantInput(user_id=U1),
                ],
            )
