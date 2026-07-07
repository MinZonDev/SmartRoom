import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SmartRoom",
  description: "Quản lý nhà trọ & chia tiền chi tiêu",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
