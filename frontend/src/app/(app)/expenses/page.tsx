"use client";

import Link from "next/link";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { createGroup, listGroups, lookupUser } from "@/lib/api";
import type { ExpenseGroup } from "@/lib/types";
import { Button, Card, ErrorText, Input } from "@/components/ui";

export default function ExpenseGroupsPage() {
  const [groups, setGroups] = useState<ExpenseGroup[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [emails, setEmails] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    listGroups().then(setGroups).catch(() => {});
  }, []);
  useEffect(load, [load]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      // Nhập email cách nhau bằng dấu phẩy -> lookup từng người lấy user_id
      const emailList = emails
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const users = await Promise.all(emailList.map(lookupUser));
      await createGroup({ name, member_ids: users.map((u) => u.id) });
      setName("");
      setEmails("");
      setShowForm(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tạo nhóm thất bại");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Nhóm chia tiền</h1>
        <Button onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Đóng" : "+ Tạo nhóm"}
        </Button>
      </div>

      {showForm && (
        <Card title="Tạo nhóm chia tiền">
          <form onSubmit={onCreate} className="space-y-3">
            <Input
              placeholder="Tên nhóm (vd: Phòng 102 chi tiêu)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              minLength={2}
            />
            <Input
              placeholder="Email thành viên, cách nhau dấu phẩy (bạn tự động là thành viên)"
              value={emails}
              onChange={(e) => setEmails(e.target.value)}
            />
            <ErrorText>{error}</ErrorText>
            <Button type="submit">Tạo nhóm</Button>
          </form>
        </Card>
      )}

      {groups.length === 0 && !showForm && (
        <p className="py-12 text-center text-sm text-gray-400">
          Chưa có nhóm nào — tạo nhóm để bắt đầu chia tiền với bạn cùng phòng.
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {groups.map((g) => (
          <Link
            key={g.id}
            href={`/expenses/${g.id}`}
            className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md"
          >
            <h2 className="font-semibold text-gray-800">{g.name}</h2>
            <p className="mt-1 text-sm text-gray-500">
              {g.members.filter((m) => !m.left_at).length} thành viên
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
