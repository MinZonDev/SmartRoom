"use client";

import { useParams } from "next/navigation";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import {
  addGroupMember,
  confirmSettlement,
  createExpense,
  createSettlement,
  fmtMoney,
  getBalances,
  getGroup,
  getSuggestions,
  listExpenses,
  listSettlements,
  lookupUser,
  me,
} from "@/lib/api";
import type {
  BalanceEntry,
  Expense,
  ExpenseGroup,
  Settlement,
  SettlementSuggestion,
} from "@/lib/types";
import { Badge, Button, Card, ErrorText, Input, Table } from "@/components/ui";

export default function ExpenseGroupDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [group, setGroup] = useState<ExpenseGroup | null>(null);
  const [myId, setMyId] = useState("");
  const [balances, setBalances] = useState<BalanceEntry[]>([]);
  const [suggestions, setSuggestions] = useState<SettlementSuggestion[]>([]);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [settlements, setSettlements] = useState<Settlement[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    getGroup(id).then(setGroup).catch(() => {});
    getBalances(id).then(setBalances).catch(() => {});
    getSuggestions(id).then(setSuggestions).catch(() => {});
    listExpenses(id).then(setExpenses).catch(() => {});
    listSettlements(id).then(setSettlements).catch(() => {});
  }, [id]);

  useEffect(() => {
    me().then((u) => setMyId(u.id)).catch(() => {});
    load();
  }, [load]);

  const memberName = useCallback(
    (userId: string) =>
      group?.members.find((m) => m.user.id === userId)?.user.full_name ??
      userId.slice(0, 8),
    [group],
  );

  async function run(action: () => Promise<unknown>) {
    setError("");
    try {
      await action();
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi");
    }
  }

  if (!group) return <p className="text-sm text-gray-400">Đang tải...</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">{group.name}</h1>
          <p className="text-sm text-gray-500">
            {group.members
              .filter((m) => !m.left_at)
              .map((m) => m.user.full_name)
              .join(" · ")}
          </p>
        </div>
        <AddMemberForm onAdd={(userId) => run(() => addGroupMember(id, userId))} />
      </div>
      <ErrorText>{error}</ErrorText>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Số dư thành viên">
          <ul className="space-y-2">
            {balances.map((b) => {
              const value = Number(b.balance);
              return (
                <li key={b.user_id} className="flex justify-between text-sm">
                  <span>
                    {b.full_name}
                    {b.user_id === myId && (
                      <span className="text-gray-400"> (bạn)</span>
                    )}
                  </span>
                  <span
                    className={`font-medium ${
                      value > 0
                        ? "text-green-600"
                        : value < 0
                          ? "text-red-600"
                          : "text-gray-500"
                    }`}
                  >
                    {value > 0 ? "+" : ""}
                    {fmtMoney(b.balance)}
                  </span>
                </li>
              );
            })}
          </ul>
        </Card>

        <Card title="Gợi ý trả nợ (số giao dịch tối thiểu)">
          {suggestions.length === 0 ? (
            <p className="text-sm text-gray-400">Cả nhóm đã cân bằng 🎉</p>
          ) : (
            <ul className="space-y-2">
              {suggestions.map((s, i) => (
                <li
                  key={i}
                  className="flex items-center justify-between text-sm"
                >
                  <span>
                    <span className="font-medium">{s.from_name}</span> trả{" "}
                    <span className="font-medium">{s.to_name}</span>{" "}
                    <span className="text-indigo-600">{fmtMoney(s.amount)}</span>
                  </span>
                  {s.from_user_id === myId && (
                    <Button
                      variant="secondary"
                      onClick={() =>
                        run(() =>
                          createSettlement(id, {
                            to_user_id: s.to_user_id,
                            amount: Number(s.amount),
                          }),
                        )
                      }
                    >
                      Tôi đã trả
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card title="Ghi khoản chi mới (chia đều cả nhóm)">
        <AddExpenseForm onAdd={(title, amount) =>
          run(() => createExpense(id, { title, amount, split_method: "equal" }))
        } />
      </Card>

      <Card title={`Lịch sử chi tiêu (${expenses.length})`}>
        <Table headers={["Ngày", "Khoản chi", "Người trả", "Số tiền", "Chia"]}>
          {expenses.map((e) => (
            <tr key={e.id}>
              <td className="px-3 py-2 text-gray-500">{e.expense_date}</td>
              <td className="px-3 py-2 font-medium">{e.title}</td>
              <td className="px-3 py-2">{memberName(e.payer_id)}</td>
              <td className="px-3 py-2">{fmtMoney(e.amount)}</td>
              <td className="px-3 py-2 text-xs text-gray-400">
                {e.split_method} · {e.shares.length} người
              </td>
            </tr>
          ))}
        </Table>
      </Card>

      <Card title="Giao dịch trả nợ">
        <Table headers={["Từ", "Đến", "Số tiền", "Trạng thái", ""]}>
          {settlements.map((s) => (
            <tr key={s.id}>
              <td className="px-3 py-2">{memberName(s.from_user_id)}</td>
              <td className="px-3 py-2">{memberName(s.to_user_id)}</td>
              <td className="px-3 py-2">{fmtMoney(s.amount)}</td>
              <td className="px-3 py-2">
                <Badge
                  color={
                    s.status === "completed"
                      ? "green"
                      : s.status === "pending"
                        ? "yellow"
                        : "gray"
                  }
                >
                  {s.status === "completed"
                    ? "Hoàn tất"
                    : s.status === "pending"
                      ? "Chờ xác nhận"
                      : "Đã hủy"}
                </Badge>
              </td>
              <td className="px-3 py-2 text-right">
                {s.status === "pending" && s.to_user_id === myId && (
                  <Button onClick={() => run(() => confirmSettlement(id, s.id))}>
                    Xác nhận đã nhận
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </Table>
      </Card>
    </div>
  );
}

function AddMemberForm({ onAdd }: { onAdd: (userId: string) => void }) {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const user = await lookupUser(email);
      onAdd(user.id);
      setEmail("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi");
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex items-center gap-2">
      <Input
        type="email"
        placeholder="Email thành viên mới"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
        className="w-52"
      />
      <Button type="submit" variant="secondary">
        + Thêm
      </Button>
      <ErrorText>{error}</ErrorText>
    </form>
  );
}

function AddExpenseForm({
  onAdd,
}: {
  onAdd: (title: string, amount: number) => void;
}) {
  const [title, setTitle] = useState("");
  const [amount, setAmount] = useState("");

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    onAdd(title, Number(amount));
    setTitle("");
    setAmount("");
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-wrap items-center gap-3">
      <Input
        placeholder="Nội dung (vd: Tiền điện tháng 7)"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        required
        className="w-64"
      />
      <Input
        type="number"
        placeholder="Số tiền"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
        required
        min={1}
        className="w-40"
      />
      <Button type="submit">Ghi khoản chi</Button>
    </form>
  );
}
