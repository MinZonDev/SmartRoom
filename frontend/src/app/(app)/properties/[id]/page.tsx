"use client";

import { useParams } from "next/navigation";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import {
  activateContract,
  closeMonth,
  createContract,
  createRoom,
  createService,
  fmtMoney,
  fmtPeriod,
  getBillingJob,
  getInvoicePdfUrl,
  getProperty,
  listContracts,
  listInvoices,
  listRooms,
  listServices,
  lookupUser,
  terminateContract,
  upsertMeterReading,
} from "@/lib/api";
import type {
  BillingJob,
  Contract,
  Invoice,
  Property,
  Room,
  UtilityService,
} from "@/lib/types";
import { Badge, Button, Card, ErrorText, Input, Select, Table } from "@/components/ui";

const TABS = [
  { key: "rooms", label: "Phòng" },
  { key: "services", label: "Dịch vụ" },
  { key: "contracts", label: "Hợp đồng" },
  { key: "billing", label: "Hóa đơn" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

const ROOM_STATUS_BADGE = {
  available: { color: "green", label: "Trống" },
  occupied: { color: "blue", label: "Đang ở" },
  maintenance: { color: "yellow", label: "Bảo trì" },
} as const;

const CONTRACT_STATUS_BADGE = {
  pending: { color: "yellow", label: "Chờ kích hoạt" },
  active: { color: "green", label: "Hiệu lực" },
  expired: { color: "gray", label: "Hết hạn" },
  terminated: { color: "gray", label: "Đã chấm dứt" },
} as const;

export default function PropertyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [property, setProperty] = useState<Property | null>(null);
  const [tab, setTab] = useState<TabKey>("rooms");

  useEffect(() => {
    getProperty(id).then(setProperty).catch(() => {});
  }, [id]);

  if (!property) return <p className="text-sm text-gray-400">Đang tải...</p>;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">{property.name}</h1>
        <p className="text-sm text-gray-500">{property.address}</p>
      </div>
      <div className="flex gap-1 border-b border-gray-200">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium ${
              tab === t.key
                ? "border-b-2 border-indigo-600 text-indigo-600"
                : "text-gray-500 hover:text-gray-800"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "rooms" && <RoomsTab propertyId={id} />}
      {tab === "services" && <ServicesTab propertyId={id} />}
      {tab === "contracts" && <ContractsTab propertyId={id} />}
      {tab === "billing" && <BillingTab propertyId={id} />}
    </div>
  );
}

// ------------------------------------------------------------------- Phòng

function RoomsTab({ propertyId }: { propertyId: string }) {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [services, setServices] = useState<UtilityService[]>([]);
  const [code, setCode] = useState("");
  const [price, setPrice] = useState("");
  const [error, setError] = useState("");
  const [meterRoom, setMeterRoom] = useState<Room | null>(null);

  const load = useCallback(() => {
    listRooms(propertyId).then(setRooms).catch(() => {});
    listServices(propertyId).then(setServices).catch(() => {});
  }, [propertyId]);
  useEffect(load, [load]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await createRoom(propertyId, { code, base_price: Number(price) });
      setCode("");
      setPrice("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi");
    }
  }

  return (
    <div className="space-y-4">
      <Card title="Thêm phòng">
        <form onSubmit={onCreate} className="flex flex-wrap items-start gap-3">
          <Input
            placeholder="Mã phòng (P101)"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            required
            className="w-40"
          />
          <Input
            type="number"
            placeholder="Giá phòng (VND)"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            required
            min={0}
            className="w-48"
          />
          <Button type="submit">Thêm</Button>
        </form>
        <ErrorText>{error}</ErrorText>
      </Card>

      <Card title={`Danh sách phòng (${rooms.length})`}>
        <Table headers={["Mã", "Giá", "Tối đa", "Trạng thái", ""]}>
          {rooms.map((r) => {
            const badge = ROOM_STATUS_BADGE[r.status];
            return (
              <tr key={r.id}>
                <td className="px-3 py-2 font-medium">{r.code}</td>
                <td className="px-3 py-2">{fmtMoney(r.base_price)}</td>
                <td className="px-3 py-2">{r.max_occupants} người</td>
                <td className="px-3 py-2">
                  <Badge color={badge.color}>{badge.label}</Badge>
                </td>
                <td className="px-3 py-2 text-right">
                  <Button
                    variant="secondary"
                    onClick={() => setMeterRoom(meterRoom?.id === r.id ? null : r)}
                  >
                    Ghi chỉ số
                  </Button>
                </td>
              </tr>
            );
          })}
        </Table>
        {meterRoom && (
          <MeterForm
            room={meterRoom}
            services={services.filter((s) => s.charge_type === "per_unit")}
            onDone={() => setMeterRoom(null)}
          />
        )}
      </Card>
    </div>
  );
}

function MeterForm({
  room,
  services,
  onDone,
}: {
  room: Room;
  services: UtilityService[];
  onDone: () => void;
}) {
  const [serviceId, setServiceId] = useState(services[0]?.id ?? "");
  const [period, setPeriod] = useState("");
  const [prev, setPrev] = useState("");
  const [curr, setCurr] = useState("");
  const [message, setMessage] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setMessage("");
    try {
      await upsertMeterReading(room.id, {
        service_id: serviceId,
        period: `${period}-01`,
        previous_value: Number(prev),
        current_value: Number(curr),
      });
      setMessage("Đã lưu chỉ số ✓");
      setTimeout(onDone, 800);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Lỗi");
    }
  }

  if (services.length === 0) {
    return (
      <p className="mt-3 text-sm text-gray-500">
        Chưa có dịch vụ tính theo chỉ số (per_unit) — thêm ở tab Dịch vụ trước.
      </p>
    );
  }

  return (
    <form
      onSubmit={onSubmit}
      className="mt-3 flex flex-wrap items-center gap-3 rounded-md bg-gray-50 p-3"
    >
      <span className="text-sm font-medium">Chỉ số {room.code}:</span>
      <Select value={serviceId} onChange={(e) => setServiceId(e.target.value)}>
        {services.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name} ({s.unit})
          </option>
        ))}
      </Select>
      <Input
        type="month"
        value={period}
        onChange={(e) => setPeriod(e.target.value)}
        required
        className="w-40"
      />
      <Input
        type="number"
        placeholder="Chỉ số cũ"
        value={prev}
        onChange={(e) => setPrev(e.target.value)}
        required
        className="w-28"
      />
      <Input
        type="number"
        placeholder="Chỉ số mới"
        value={curr}
        onChange={(e) => setCurr(e.target.value)}
        required
        className="w-28"
      />
      <Button type="submit">Lưu</Button>
      <span className="text-sm text-gray-600">{message}</span>
    </form>
  );
}

// ----------------------------------------------------------------- Dịch vụ

const CHARGE_TYPE_LABEL = {
  per_unit: "Theo chỉ số",
  per_person: "Theo đầu người",
  per_room: "Theo phòng",
  flat: "Cố định",
} as const;

function ServicesTab({ propertyId }: { propertyId: string }) {
  const [services, setServices] = useState<UtilityService[]>([]);
  const [name, setName] = useState("");
  const [unit, setUnit] = useState("");
  const [price, setPrice] = useState("");
  const [chargeType, setChargeType] = useState("per_unit");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    listServices(propertyId).then(setServices).catch(() => {});
  }, [propertyId]);
  useEffect(load, [load]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await createService(propertyId, {
        name,
        unit: unit || undefined,
        unit_price: Number(price),
        charge_type: chargeType,
      });
      setName("");
      setUnit("");
      setPrice("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi");
    }
  }

  return (
    <div className="space-y-4">
      <Card title="Thêm dịch vụ (điện, nước, internet, rác...)">
        <form onSubmit={onCreate} className="flex flex-wrap items-start gap-3">
          <Input
            placeholder="Tên (Điện)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="w-36"
          />
          <Input
            placeholder="Đơn vị (kWh)"
            value={unit}
            onChange={(e) => setUnit(e.target.value)}
            className="w-32"
          />
          <Input
            type="number"
            placeholder="Đơn giá"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            required
            min={0}
            className="w-36"
          />
          <Select value={chargeType} onChange={(e) => setChargeType(e.target.value)}>
            {Object.entries(CHARGE_TYPE_LABEL).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </Select>
          <Button type="submit">Thêm</Button>
        </form>
        <ErrorText>{error}</ErrorText>
      </Card>

      <Card title="Danh sách dịch vụ">
        <Table headers={["Tên", "Đơn giá", "Cách tính", "Trạng thái"]}>
          {services.map((s) => (
            <tr key={s.id}>
              <td className="px-3 py-2 font-medium">
                {s.name} {s.unit && <span className="text-gray-400">({s.unit})</span>}
              </td>
              <td className="px-3 py-2">{fmtMoney(s.unit_price)}</td>
              <td className="px-3 py-2">{CHARGE_TYPE_LABEL[s.charge_type]}</td>
              <td className="px-3 py-2">
                <Badge color={s.is_active ? "green" : "gray"}>
                  {s.is_active ? "Đang dùng" : "Đã tắt"}
                </Badge>
              </td>
            </tr>
          ))}
        </Table>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------- Hợp đồng

function ContractsTab({ propertyId }: { propertyId: string }) {
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [roomId, setRoomId] = useState("");
  const [tenantEmail, setTenantEmail] = useState("");
  const [rent, setRent] = useState("");
  const [deposit, setDeposit] = useState("");
  const [startDate, setStartDate] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    listContracts(propertyId).then(setContracts).catch(() => {});
    listRooms(propertyId).then(setRooms).catch(() => {});
  }, [propertyId]);
  useEffect(load, [load]);

  const roomCode = (rid: string) => rooms.find((r) => r.id === rid)?.code ?? "?";

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const tenant = await lookupUser(tenantEmail); // email -> user_id
      await createContract({
        room_id: roomId,
        monthly_rent: Number(rent),
        deposit_amount: Number(deposit || 0),
        start_date: startDate,
        members: [{ user_id: tenant.id, is_primary: true }],
      });
      setTenantEmail("");
      setRent("");
      setDeposit("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi");
    }
  }

  async function doAction(action: () => Promise<Contract>) {
    setError("");
    try {
      await action();
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi");
    }
  }

  return (
    <div className="space-y-4">
      <Card title="Tạo hợp đồng mới">
        <form onSubmit={onCreate} className="flex flex-wrap items-start gap-3">
          <Select value={roomId} onChange={(e) => setRoomId(e.target.value)} required>
            <option value="">-- Chọn phòng --</option>
            {rooms.map((r) => (
              <option key={r.id} value={r.id}>
                {r.code}
              </option>
            ))}
          </Select>
          <Input
            type="email"
            placeholder="Email khách thuê"
            value={tenantEmail}
            onChange={(e) => setTenantEmail(e.target.value)}
            required
            className="w-56"
          />
          <Input
            type="number"
            placeholder="Tiền thuê/tháng"
            value={rent}
            onChange={(e) => setRent(e.target.value)}
            required
            className="w-40"
          />
          <Input
            type="number"
            placeholder="Tiền cọc"
            value={deposit}
            onChange={(e) => setDeposit(e.target.value)}
            className="w-36"
          />
          <Input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            required
            className="w-40"
          />
          <Button type="submit">Tạo</Button>
        </form>
        <ErrorText>{error}</ErrorText>
        <p className="mt-2 text-xs text-gray-400">
          Khách thuê phải có tài khoản SmartRoom (tìm theo email).
        </p>
      </Card>

      <Card title={`Hợp đồng (${contracts.length})`}>
        <Table headers={["Mã", "Phòng", "Tiền thuê", "Người ở", "Trạng thái", ""]}>
          {contracts.map((c) => {
            const badge = CONTRACT_STATUS_BADGE[c.status];
            return (
              <tr key={c.id}>
                <td className="px-3 py-2 font-medium">{c.code}</td>
                <td className="px-3 py-2">{roomCode(c.room_id)}</td>
                <td className="px-3 py-2">{fmtMoney(c.monthly_rent)}</td>
                <td className="px-3 py-2">
                  {c.members.filter((m) => !m.left_at).length}
                </td>
                <td className="px-3 py-2">
                  <Badge color={badge.color}>{badge.label}</Badge>
                </td>
                <td className="space-x-2 px-3 py-2 text-right">
                  {c.status === "pending" && (
                    <Button onClick={() => doAction(() => activateContract(c.id))}>
                      Kích hoạt
                    </Button>
                  )}
                  {(c.status === "pending" || c.status === "active") && (
                    <Button
                      variant="danger"
                      onClick={() => {
                        if (confirm(`Chấm dứt hợp đồng ${c.code}?`)) {
                          doAction(() => terminateContract(c.id));
                        }
                      }}
                    >
                      Chấm dứt
                    </Button>
                  )}
                </td>
              </tr>
            );
          })}
        </Table>
      </Card>
    </div>
  );
}

// ----------------------------------------------------------------- Hóa đơn

const INVOICE_STATUS_BADGE = {
  draft: { color: "gray", label: "Nháp" },
  issued: { color: "blue", label: "Đã phát hành" },
  partially_paid: { color: "yellow", label: "Trả một phần" },
  paid: { color: "green", label: "Đã thanh toán" },
  overdue: { color: "red", label: "Quá hạn" },
  cancelled: { color: "gray", label: "Đã hủy" },
} as const;

function BillingTab({ propertyId }: { propertyId: string }) {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [period, setPeriod] = useState("");
  const [job, setJob] = useState<BillingJob | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  const loadInvoices = useCallback(() => {
    listInvoices(propertyId).then(setInvoices).catch(() => {});
  }, [propertyId]);
  useEffect(loadInvoices, [loadInvoices]);

  async function onCloseMonth(e: FormEvent) {
    e.preventDefault();
    setError("");
    setJob(null);
    setRunning(true);
    try {
      const accepted = await closeMonth(propertyId, `${period}-01`);
      // Poll trạng thái job mỗi 1.5s — API trả 202, worker xử lý nền qua SQS
      const timer = setInterval(async () => {
        try {
          const j = await getBillingJob(accepted.job_id);
          setJob(j);
          if (j.status === "completed" || j.status === "failed") {
            clearInterval(timer);
            setRunning(false);
            loadInvoices();
          }
        } catch {
          clearInterval(timer);
          setRunning(false);
        }
      }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi");
      setRunning(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card title="Chốt tháng — sinh hóa đơn hàng loạt">
        <form onSubmit={onCloseMonth} className="flex flex-wrap items-center gap-3">
          <Input
            type="month"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            required
            className="w-44"
          />
          <Button type="submit" disabled={running}>
            {running ? "Đang xử lý..." : "Chốt tháng"}
          </Button>
          {job && (
            <span className="text-sm">
              {job.status === "completed" && job.result ? (
                <span className="text-green-700">
                  ✓ Tạo {job.result.invoices_created} hóa đơn
                  {job.result.skipped.length > 0 &&
                    `, bỏ qua ${job.result.skipped.length}`}
                  {job.result.errors.length > 0 && (
                    <span className="text-red-600">
                      , lỗi: {job.result.errors.join("; ")}
                    </span>
                  )}
                </span>
              ) : job.status === "failed" ? (
                <span className="text-red-600">✗ {job.error}</span>
              ) : (
                <span className="text-gray-500">Đang xử lý ({job.status})...</span>
              )}
            </span>
          )}
        </form>
        <ErrorText>{error}</ErrorText>
      </Card>

      <Card title={`Hóa đơn (${invoices.length})`}>
        <Table headers={["Mã", "Kỳ", "Tổng tiền", "Đã trả", "Trạng thái", "PDF"]}>
          {invoices.map((inv) => {
            const badge = INVOICE_STATUS_BADGE[inv.status];
            return (
              <tr key={inv.id}>
                <td className="px-3 py-2 font-medium">{inv.code}</td>
                <td className="px-3 py-2">{fmtPeriod(inv.period)}</td>
                <td className="px-3 py-2">{fmtMoney(inv.total_amount)}</td>
                <td className="px-3 py-2">{fmtMoney(inv.paid_amount)}</td>
                <td className="px-3 py-2">
                  <Badge color={badge.color}>{badge.label}</Badge>
                </td>
                <td className="px-3 py-2">
                  {inv.pdf_url ? (
                    <Button
                      variant="secondary"
                      onClick={async () => {
                        // Presigned URL hết hạn 15' — xin mới mỗi lần bấm
                        const { url } = await getInvoicePdfUrl(inv.id);
                        window.open(url, "_blank");
                      }}
                    >
                      Tải PDF
                    </Button>
                  ) : (
                    <span className="text-xs text-gray-400">—</span>
                  )}
                </td>
              </tr>
            );
          })}
        </Table>
      </Card>
    </div>
  );
}
