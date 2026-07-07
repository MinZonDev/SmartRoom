"""Business logic module expenses — mô hình Splitwise.

Nguyên tắc:
- Authorization theo MEMBERSHIP: mọi thao tác yêu cầu là thành viên đang
  hoạt động của nhóm (người ngoài nhận 404 — không lộ nhóm tồn tại).
- SUM(shares) == amount là bất biến (DB không ép được): thuật toán chia
  ROUND_DOWN + phân phối phần dư đảm bảo tổng khớp tuyệt đối.
- Số dư KHÔNG lưu — luôn tính từ dữ liệu gốc (expenses/shares/settlements
  completed) nên không bao giờ lệch sổ.
"""

from datetime import date, datetime, timezone
from decimal import ROUND_DOWN, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models import User
from app.modules.expenses.models import (
    Expense,
    ExpenseGroup,
    ExpenseGroupMember,
    ExpenseShare,
    Settlement,
)
from app.modules.expenses.schemas import (
    AddGroupMemberRequest,
    BalanceEntry,
    ExpenseCreate,
    GroupCreate,
    SettlementCreate,
    SettlementSuggestion,
)
from app.shared.enums import SettlementStatus, SplitMethod
from app.shared.exceptions import ConflictError, NotFoundError, PermissionDeniedError

_CENT = Decimal("0.01")


class ExpenseService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -------------------------------------------------------------- groups

    async def create_group(self, creator_id: UUID, payload: GroupCreate) -> ExpenseGroup:
        member_ids = {*payload.member_ids, creator_id}  # người tạo luôn là thành viên
        await self._ensure_users_exist(list(member_ids))
        group = ExpenseGroup(
            name=payload.name,
            created_by=creator_id,
            members=[ExpenseGroupMember(user_id=uid) for uid in member_ids],
        )
        self._session.add(group)
        await self._session.commit()
        return await self._get_group_for_member(group.id, creator_id)

    async def list_my_groups(self, user_id: UUID) -> list[ExpenseGroup]:
        result = await self._session.scalars(
            select(ExpenseGroup)
            .join(ExpenseGroupMember)
            .where(
                ExpenseGroupMember.user_id == user_id,
                ExpenseGroupMember.left_at.is_(None),
            )
            .options(
                selectinload(ExpenseGroup.members).selectinload(
                    ExpenseGroupMember.user
                )
            )
            .order_by(ExpenseGroup.created_at.desc())
        )
        return list(result.all())

    async def get_group(self, group_id: UUID, user_id: UUID) -> ExpenseGroup:
        return await self._get_group_for_member(group_id, user_id)

    async def add_member(
        self, group_id: UUID, user_id: UUID, payload: AddGroupMemberRequest
    ) -> ExpenseGroup:
        await self._get_group_for_member(group_id, user_id)
        await self._ensure_users_exist([payload.user_id])

        existing = await self._session.get(
            ExpenseGroupMember, (group_id, payload.user_id)
        )
        if existing is not None:
            if existing.left_at is None:
                raise ConflictError("User đã là thành viên của nhóm")
            existing.left_at = None  # rejoin: mở lại membership cũ
            existing.joined_at = datetime.now(timezone.utc)
        else:
            self._session.add(
                ExpenseGroupMember(group_id=group_id, user_id=payload.user_id)
            )
        await self._session.commit()
        return await self._get_group_for_member(group_id, user_id)

    # ------------------------------------------------------------ expenses

    async def create_expense(
        self, group_id: UUID, user_id: UUID, payload: ExpenseCreate
    ) -> Expense:
        await self._get_group_for_member(group_id, user_id)
        active_ids = await self._active_member_ids(group_id)

        payer_id = payload.payer_id or user_id
        if payer_id not in active_ids:
            raise ConflictError("Người trả phải là thành viên đang ở trong nhóm")

        if payload.participants is not None:
            outsiders = {p.user_id for p in payload.participants} - active_ids
            if outsiders:
                raise ConflictError(
                    "Participant không phải thành viên đang ở: "
                    + ", ".join(str(u) for u in outsiders)
                )

        shares = self._compute_shares(payload, sorted(active_ids, key=str))
        expense = Expense(
            group_id=group_id,
            payer_id=payer_id,
            title=payload.title,
            amount=payload.amount,
            expense_date=payload.expense_date or date.today(),
            split_method=payload.split_method,
            receipt_image_url=payload.receipt_image_url,
            note=payload.note,
            shares=[
                ExpenseShare(user_id=uid, share_amount=amount)
                for uid, amount in shares
            ],
        )
        self._session.add(expense)
        await self._session.commit()
        return expense

    async def list_expenses(self, group_id: UUID, user_id: UUID) -> list[Expense]:
        await self._get_group_for_member(group_id, user_id)
        result = await self._session.scalars(
            select(Expense)
            .where(Expense.group_id == group_id)
            .options(selectinload(Expense.shares))
            .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
        )
        return list(result.all())

    async def delete_expense(
        self, group_id: UUID, expense_id: UUID, user_id: UUID
    ) -> None:
        await self._get_group_for_member(group_id, user_id)
        expense = await self._session.scalar(
            select(Expense).where(
                Expense.id == expense_id, Expense.group_id == group_id
            )
        )
        if expense is None:
            raise NotFoundError("Khoản chi không tồn tại")
        if expense.payer_id != user_id:
            raise PermissionDeniedError("Chỉ người trả mới xóa được khoản chi")
        await self._session.delete(expense)  # cascade xóa shares
        await self._session.commit()

    # ------------------------------------------------------------- balances

    async def get_balances(self, group_id: UUID, user_id: UUID) -> list[BalanceEntry]:
        """balance = Σ(đã trả) − Σ(phải chịu) + Σ(settlement gửi) − Σ(settlement nhận).

        Chỉ tính settlement COMPLETED — pending chưa phải là tiền đã trao.
        Gồm cả thành viên đã rời (họ có thể còn nợ cũ).
        """
        await self._get_group_for_member(group_id, user_id)

        members = (
            await self._session.execute(
                select(ExpenseGroupMember.user_id, User.full_name)
                .join(User, ExpenseGroupMember.user_id == User.id)
                .where(ExpenseGroupMember.group_id == group_id)
            )
        ).all()

        paid = dict(
            (
                await self._session.execute(
                    select(Expense.payer_id, func.sum(Expense.amount))
                    .where(Expense.group_id == group_id)
                    .group_by(Expense.payer_id)
                )
            ).all()
        )
        owed = dict(
            (
                await self._session.execute(
                    select(ExpenseShare.user_id, func.sum(ExpenseShare.share_amount))
                    .join(Expense, ExpenseShare.expense_id == Expense.id)
                    .where(Expense.group_id == group_id)
                    .group_by(ExpenseShare.user_id)
                )
            ).all()
        )
        sent = dict(
            (
                await self._session.execute(
                    select(Settlement.from_user_id, func.sum(Settlement.amount))
                    .where(
                        Settlement.group_id == group_id,
                        Settlement.status == SettlementStatus.COMPLETED,
                    )
                    .group_by(Settlement.from_user_id)
                )
            ).all()
        )
        received = dict(
            (
                await self._session.execute(
                    select(Settlement.to_user_id, func.sum(Settlement.amount))
                    .where(
                        Settlement.group_id == group_id,
                        Settlement.status == SettlementStatus.COMPLETED,
                    )
                    .group_by(Settlement.to_user_id)
                )
            ).all()
        )

        zero = Decimal("0")
        return [
            BalanceEntry(
                user_id=uid,
                full_name=name,
                balance=paid.get(uid, zero)
                - owed.get(uid, zero)
                + sent.get(uid, zero)
                - received.get(uid, zero),
            )
            for uid, name in members
        ]

    async def suggest_settlements(
        self, group_id: UUID, user_id: UUID
    ) -> list[SettlementSuggestion]:
        """Greedy min-cash-flow: ghép người nợ nhiều nhất với người được nhận
        nhiều nhất — số giao dịch tối thiểu để cả nhóm về 0.
        """
        balances = await self.get_balances(group_id, user_id)
        names = {b.user_id: b.full_name for b in balances}
        creditors = sorted(
            ((b.user_id, b.balance) for b in balances if b.balance > 0),
            key=lambda x: x[1],
            reverse=True,
        )
        debtors = sorted(
            ((b.user_id, -b.balance) for b in balances if b.balance < 0),
            key=lambda x: x[1],
            reverse=True,
        )

        suggestions: list[SettlementSuggestion] = []
        i = j = 0
        while i < len(debtors) and j < len(creditors):
            debtor_id, debt = debtors[i]
            creditor_id, credit = creditors[j]
            amount = min(debt, credit)
            if amount > 0:
                suggestions.append(
                    SettlementSuggestion(
                        from_user_id=debtor_id,
                        from_name=names[debtor_id],
                        to_user_id=creditor_id,
                        to_name=names[creditor_id],
                        amount=amount,
                    )
                )
            debtors[i] = (debtor_id, debt - amount)
            creditors[j] = (creditor_id, credit - amount)
            if debtors[i][1] == 0:
                i += 1
            if creditors[j][1] == 0:
                j += 1
        return suggestions

    # ---------------------------------------------------------- settlements

    async def create_settlement(
        self, group_id: UUID, from_user_id: UUID, payload: SettlementCreate
    ) -> Settlement:
        """Người TRẢ NỢ ghi nhận giao dịch (pending) — người nhận confirm sau."""
        await self._get_group_for_member(group_id, from_user_id)
        active_ids = await self._active_member_ids(group_id)
        if payload.to_user_id not in active_ids:
            raise ConflictError("Người nhận phải là thành viên đang ở trong nhóm")
        if payload.to_user_id == from_user_id:
            raise ConflictError("Không thể tự trả nợ cho chính mình")

        settlement = Settlement(
            group_id=group_id,
            from_user_id=from_user_id,
            to_user_id=payload.to_user_id,
            amount=payload.amount,
        )
        self._session.add(settlement)
        await self._session.commit()
        return settlement

    async def list_settlements(
        self, group_id: UUID, user_id: UUID
    ) -> list[Settlement]:
        await self._get_group_for_member(group_id, user_id)
        result = await self._session.scalars(
            select(Settlement)
            .where(Settlement.group_id == group_id)
            .order_by(Settlement.created_at.desc())
        )
        return list(result.all())

    async def confirm_settlement(
        self, group_id: UUID, settlement_id: UUID, user_id: UUID
    ) -> Settlement:
        settlement = await self._get_settlement(group_id, settlement_id, user_id)
        if settlement.to_user_id != user_id:
            raise PermissionDeniedError("Chỉ người nhận tiền mới xác nhận được")
        if settlement.status != SettlementStatus.PENDING:
            raise ConflictError(f"Settlement đã ở trạng thái {settlement.status.value}")
        settlement.status = SettlementStatus.COMPLETED
        settlement.settled_at = datetime.now(timezone.utc)
        await self._session.commit()
        return settlement

    async def cancel_settlement(
        self, group_id: UUID, settlement_id: UUID, user_id: UUID
    ) -> Settlement:
        settlement = await self._get_settlement(group_id, settlement_id, user_id)
        if user_id not in (settlement.from_user_id, settlement.to_user_id):
            raise PermissionDeniedError("Chỉ 2 bên liên quan mới hủy được")
        if settlement.status != SettlementStatus.PENDING:
            raise ConflictError(f"Settlement đã ở trạng thái {settlement.status.value}")
        settlement.status = SettlementStatus.CANCELLED
        await self._session.commit()
        return settlement

    # -------------------------------------------------------------- helpers

    def _compute_shares(
        self, payload: ExpenseCreate, default_participants: list[UUID]
    ) -> list[tuple[UUID, Decimal]]:
        """Tính phần mỗi người. Bất biến: tổng shares == amount (đến 0.01).

        ROUND_DOWN từng phần rồi phân phối phần dư 0.01/lượt cho các người
        đầu danh sách — không bao giờ lệch tổng do làm tròn.
        """
        if payload.split_method == SplitMethod.EXACT:
            assert payload.participants is not None  # đã validate ở schema
            return [(p.user_id, p.amount) for p in payload.participants]  # type: ignore[misc]

        if payload.split_method == SplitMethod.RATIO:
            assert payload.participants is not None
            total_weight = sum(p.weight for p in payload.participants)  # type: ignore[misc]
            raw = [
                (
                    p.user_id,
                    (payload.amount * p.weight / total_weight).quantize(  # type: ignore[operator]
                        _CENT, rounding=ROUND_DOWN
                    ),
                )
                for p in payload.participants
            ]
        else:  # EQUAL
            ids = (
                [p.user_id for p in payload.participants]
                if payload.participants
                else default_participants
            )
            base = (payload.amount / len(ids)).quantize(_CENT, rounding=ROUND_DOWN)
            raw = [(uid, base) for uid in ids]

        # Phần dư = amount − Σ(đã ROUND_DOWN), luôn là bội số 0.01 và < n×0.01
        # -> phát 0.01/người từ đầu danh sách cho tới hết là tổng khớp tuyệt đối
        remainder = payload.amount - sum(amount for _, amount in raw)
        shares: list[tuple[UUID, Decimal]] = []
        for uid, amount in raw:
            extra = min(_CENT, remainder)
            shares.append((uid, amount + extra))
            remainder -= extra
        return shares

    async def _get_group_for_member(
        self, group_id: UUID, user_id: UUID
    ) -> ExpenseGroup:
        group = await self._session.scalar(
            select(ExpenseGroup)
            .join(ExpenseGroupMember)
            .where(
                ExpenseGroup.id == group_id,
                ExpenseGroupMember.user_id == user_id,
                ExpenseGroupMember.left_at.is_(None),
            )
            .options(
                selectinload(ExpenseGroup.members).selectinload(
                    ExpenseGroupMember.user
                )
            )
        )
        if group is None:
            raise NotFoundError("Nhóm không tồn tại hoặc bạn không phải thành viên")
        return group

    async def _active_member_ids(self, group_id: UUID) -> set[UUID]:
        result = await self._session.scalars(
            select(ExpenseGroupMember.user_id).where(
                ExpenseGroupMember.group_id == group_id,
                ExpenseGroupMember.left_at.is_(None),
            )
        )
        return set(result.all())

    async def _get_settlement(
        self, group_id: UUID, settlement_id: UUID, user_id: UUID
    ) -> Settlement:
        await self._get_group_for_member(group_id, user_id)
        settlement = await self._session.scalar(
            select(Settlement).where(
                Settlement.id == settlement_id, Settlement.group_id == group_id
            )
        )
        if settlement is None:
            raise NotFoundError("Settlement không tồn tại")
        return settlement

    async def _ensure_users_exist(self, user_ids: list[UUID]) -> None:
        found = (
            await self._session.scalars(select(User.id).where(User.id.in_(user_ids)))
        ).all()
        missing = set(user_ids) - set(found)
        if missing:
            raise NotFoundError(
                f"User không tồn tại: {', '.join(str(u) for u in missing)}"
            )
