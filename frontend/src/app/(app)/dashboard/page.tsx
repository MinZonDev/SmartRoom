"use client";

import Link from "next/link";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { createProperty, listProperties } from "@/lib/api";
import type { Property } from "@/lib/types";
import { Button, Card, ErrorText, Input } from "@/components/ui";

export default function DashboardPage() {
  const [properties, setProperties] = useState<Property[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    listProperties().then(setProperties).catch(() => {});
  }, []);

  useEffect(load, [load]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await createProperty({ name, address, city: city || undefined });
      setName("");
      setAddress("");
      setCity("");
      setShowForm(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tạo thất bại");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Nhà trọ của tôi</h1>
        <Button onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Đóng" : "+ Thêm nhà trọ"}
        </Button>
      </div>

      {showForm && (
        <Card title="Thêm nhà trọ mới">
          <form onSubmit={onCreate} className="grid gap-3 sm:grid-cols-3">
            <Input
              placeholder="Tên (vd: Nhà trọ Bình An)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              minLength={2}
            />
            <Input
              placeholder="Địa chỉ"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              required
              minLength={5}
            />
            <Input
              placeholder="Thành phố (tùy chọn)"
              value={city}
              onChange={(e) => setCity(e.target.value)}
            />
            <div className="sm:col-span-3">
              <ErrorText>{error}</ErrorText>
              <Button type="submit">Tạo</Button>
            </div>
          </form>
        </Card>
      )}

      {properties.length === 0 && !showForm && (
        <p className="py-12 text-center text-sm text-gray-400">
          Chưa có nhà trọ nào — bấm &quot;Thêm nhà trọ&quot; để bắt đầu.
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {properties.map((p) => (
          <Link
            key={p.id}
            href={`/properties/${p.id}`}
            className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md"
          >
            <h2 className="font-semibold text-gray-800">{p.name}</h2>
            <p className="mt-1 text-sm text-gray-500">{p.address}</p>
            {p.city && <p className="text-xs text-gray-400">{p.city}</p>}
          </Link>
        ))}
      </div>
    </div>
  );
}
