"use client";

import { useEffect, useState } from "react";

import { fmtMoney, fmtPeriod, getInvoicePdfUrl, listMyInvoices } from "@/lib/api";
import type { Invoice } from "@/lib/types";
import { Badge, Button, Card, Table } from "@/components/ui";

const STATUS_BADGE = {
  draft: { color: "gray", label: "Nháp" },
  issued: { color: "blue", label: "Chờ thanh toán" },
  partially_paid: { color: "yellow", label: "Trả một phần" },
  paid: { color: "green", label: "Đã thanh toán" },
  overdue: { color: "red", label: "Quá hạn" },
  cancelled: { color: "gray", label: "Đã hủy" },
} as const;

export default function MyInvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    listMyInvoices()
      .then(setInvoices)
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Hóa đơn của tôi</h1>
      {loaded && invoices.length === 0 ? (
        <p className="py-12 text-center text-sm text-gray-400">
          Bạn chưa có hóa đơn nào — hóa đơn xuất hiện khi bạn là thành viên hợp
          đồng thuê phòng và chủ nhà chốt tháng.
        </p>
      ) : (
        <Card>
          <Table
            headers={["Mã", "Kỳ", "Hạn thanh toán", "Tổng tiền", "Trạng thái", ""]}
          >
            {invoices.map((inv) => {
              const badge = STATUS_BADGE[inv.status];
              return (
                <tr key={inv.id}>
                  <td className="px-3 py-2 font-medium">{inv.code}</td>
                  <td className="px-3 py-2">{fmtPeriod(inv.period)}</td>
                  <td className="px-3 py-2">{inv.due_date}</td>
                  <td className="px-3 py-2 font-medium">
                    {fmtMoney(inv.total_amount)}
                  </td>
                  <td className="px-3 py-2">
                    <Badge color={badge.color}>{badge.label}</Badge>
                  </td>
                  <td className="px-3 py-2 text-right">
                    {inv.pdf_url && (
                      <Button
                        variant="secondary"
                        onClick={async () => {
                          const { url } = await getInvoicePdfUrl(inv.id);
                          window.open(url, "_blank");
                        }}
                      >
                        Tải PDF
                      </Button>
                    )}
                  </td>
                </tr>
              );
            })}
          </Table>
        </Card>
      )}
    </div>
  );
}
