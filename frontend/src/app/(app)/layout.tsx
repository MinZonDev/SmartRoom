"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { getToken, logout as apiLogout, me } from "@/lib/api";
import type { User } from "@/lib/types";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Nhà trọ" },
  { href: "/my-invoices", label: "Hóa đơn của tôi" },
  { href: "/expenses", label: "Chia tiền" },
];

export default function AppLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    me().then(setUser).catch(() => {
      /* 401 đã được api client xử lý (redirect /login) */
    });
  }, [router]);

  async function logout() {
    await apiLogout(); // thu hồi refresh token server-side rồi xóa local
    router.replace("/login");
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-6">
            <Link href="/dashboard" className="text-lg font-bold text-indigo-600">
              SmartRoom
            </Link>
            <nav className="flex gap-1">
              {NAV_ITEMS.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                    pathname.startsWith(item.href)
                      ? "bg-indigo-50 text-indigo-700"
                      : "text-gray-600 hover:bg-gray-100"
                  }`}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-gray-600">{user?.full_name}</span>
            <button
              onClick={logout}
              className="text-gray-400 hover:text-red-600"
              title="Đăng xuất"
            >
              Đăng xuất
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
    </div>
  );
}
