/**
 * API client — fetch wrapper + toàn bộ endpoint của backend.
 * Token JWT lưu localStorage; 401 tự đưa về /login.
 */

import type {
  BalanceEntry,
  BillingJob,
  CloseMonthAccepted,
  Contract,
  Expense,
  ExpenseGroup,
  Invoice,
  MeterReading,
  Property,
  Room,
  Settlement,
  SettlementSuggestion,
  TokenResponse,
  User,
  UtilityService,
} from "@/lib/types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const TOKEN_KEY = "smartroom_token";
const REFRESH_KEY = "smartroom_refresh_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

/** Đổi refresh token lấy cặp token mới. Trả false nếu hết hạn/không có. */
async function tryRefreshToken(): Promise<boolean> {
  const refreshToken =
    typeof window === "undefined" ? null : localStorage.getItem(REFRESH_KEY);
  if (!refreshToken) return false;
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return false;
    const data: TokenResponse = await res.json();
    setToken(data.access_token);
    localStorage.setItem(REFRESH_KEY, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

// Nhiều request 401 cùng lúc chỉ refresh 1 lần
let refreshInFlight: Promise<boolean> | null = null;

export class ApiError extends Error {
  constructor(
    public status: number,
    detail: string,
  ) {
    super(detail);
  }
}

interface RequestOptions {
  method?: string;
  json?: unknown;
  form?: Record<string, string>;
  formData?: FormData;
}

async function api<T>(
  path: string,
  opts: RequestOptions = {},
  isRetryAfterRefresh = false,
): Promise<T> {
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    body = new URLSearchParams(opts.form);
  } else if (opts.formData) {
    body = opts.formData; // browser tự đặt multipart boundary
  }
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body,
  });

  if (res.status === 401 && !path.startsWith("/auth/")) {
    // Access token hết hạn -> thử refresh 1 lần rồi retry request gốc
    if (!isRetryAfterRefresh) {
      refreshInFlight ??= tryRefreshToken();
      const refreshed = await refreshInFlight;
      refreshInFlight = null;
      if (refreshed) return api<T>(path, opts, true);
    }
    clearToken();
    if (typeof window !== "undefined") window.location.href = "/login";
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail =
        typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* body không phải JSON */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ---------------------------------------------------------------------- auth

export async function login(email: string, password: string): Promise<void> {
  const data = await api<TokenResponse>("/auth/login", {
    method: "POST",
    form: { username: email, password },
  });
  setToken(data.access_token);
  localStorage.setItem(REFRESH_KEY, data.refresh_token);
}

export function register(payload: {
  full_name: string;
  email: string;
  password: string;
  phone?: string;
}): Promise<User> {
  return api("/auth/register", { method: "POST", json: payload });
}

export function me(): Promise<User> {
  return api("/auth/me");
}

export function lookupUser(email: string): Promise<User> {
  return api(`/auth/users/lookup?email=${encodeURIComponent(email)}`);
}

// ---------------------------------------------------------------- properties

export function listProperties(): Promise<Property[]> {
  return api("/properties");
}

export function createProperty(payload: {
  name: string;
  address: string;
  city?: string;
  district?: string;
}): Promise<Property> {
  return api("/properties", { method: "POST", json: payload });
}

export function getProperty(id: string): Promise<Property> {
  return api(`/properties/${id}`);
}

export function listRooms(propertyId: string): Promise<Room[]> {
  return api(`/properties/${propertyId}/rooms`);
}

export function createRoom(
  propertyId: string,
  payload: { code: string; base_price: number; floor?: number; max_occupants?: number },
): Promise<Room> {
  return api(`/properties/${propertyId}/rooms`, { method: "POST", json: payload });
}

export function listServices(propertyId: string): Promise<UtilityService[]> {
  return api(`/properties/${propertyId}/services`);
}

export function createService(
  propertyId: string,
  payload: { name: string; unit?: string; unit_price: number; charge_type: string },
): Promise<UtilityService> {
  return api(`/properties/${propertyId}/services`, {
    method: "POST",
    json: payload,
  });
}

export function upsertMeterReading(
  roomId: string,
  payload: {
    service_id: string;
    period: string;
    previous_value: number;
    current_value: number;
    image_url?: string;
  },
): Promise<MeterReading> {
  return api(`/rooms/${roomId}/meter-readings`, { method: "PUT", json: payload });
}

export interface MeterOCRResult {
  value: number;
  raw_text: string;
  confidence: number;
  needs_confirmation: boolean;
  candidates: { text: string; confidence: number }[];
  image_url: string | null;
}

export function ocrMeterReading(file: File): Promise<MeterOCRResult> {
  const formData = new FormData();
  formData.append("file", file);
  return api("/ocr/meter-reading", { method: "POST", formData });
}

// ----------------------------------------------------------------- contracts

export function listContracts(propertyId: string): Promise<Contract[]> {
  return api(`/contracts?property_id=${propertyId}`);
}

export function createContract(payload: {
  room_id: string;
  monthly_rent: number;
  deposit_amount: number;
  start_date: string;
  members: { user_id: string; is_primary: boolean }[];
}): Promise<Contract> {
  return api("/contracts", { method: "POST", json: payload });
}

export function activateContract(id: string): Promise<Contract> {
  return api(`/contracts/${id}/activate`, { method: "POST" });
}

export function terminateContract(id: string): Promise<Contract> {
  return api(`/contracts/${id}/terminate`, { method: "POST" });
}

// ------------------------------------------------------------------- billing

export function closeMonth(
  propertyId: string,
  period: string,
): Promise<CloseMonthAccepted> {
  return api("/billing/close-month", {
    method: "POST",
    json: { property_id: propertyId, period },
  });
}

export function getBillingJob(jobId: string): Promise<BillingJob> {
  return api(`/billing/jobs/${jobId}`);
}

export function listInvoices(propertyId: string): Promise<Invoice[]> {
  return api(`/billing/invoices?property_id=${propertyId}`);
}

export function getInvoicePdfUrl(
  invoiceId: string,
): Promise<{ url: string; expires_in: number }> {
  return api(`/billing/invoices/${invoiceId}/pdf-url`);
}

export function listMyInvoices(): Promise<Invoice[]> {
  return api("/billing/my-invoices");
}

// ------------------------------------------------------------------ expenses

export function listGroups(): Promise<ExpenseGroup[]> {
  return api("/expense-groups");
}

export function createGroup(payload: {
  name: string;
  member_ids: string[];
}): Promise<ExpenseGroup> {
  return api("/expense-groups", { method: "POST", json: payload });
}

export function getGroup(id: string): Promise<ExpenseGroup> {
  return api(`/expense-groups/${id}`);
}

export function addGroupMember(
  groupId: string,
  userId: string,
): Promise<ExpenseGroup> {
  return api(`/expense-groups/${groupId}/members`, {
    method: "POST",
    json: { user_id: userId },
  });
}

export function listExpenses(groupId: string): Promise<Expense[]> {
  return api(`/expense-groups/${groupId}/expenses`);
}

export function createExpense(
  groupId: string,
  payload: { title: string; amount: number; split_method: string },
): Promise<Expense> {
  return api(`/expense-groups/${groupId}/expenses`, {
    method: "POST",
    json: payload,
  });
}

export function getBalances(groupId: string): Promise<BalanceEntry[]> {
  return api(`/expense-groups/${groupId}/balances`);
}

export function getSuggestions(
  groupId: string,
): Promise<SettlementSuggestion[]> {
  return api(`/expense-groups/${groupId}/settlement-suggestions`);
}

export function listSettlements(groupId: string): Promise<Settlement[]> {
  return api(`/expense-groups/${groupId}/settlements`);
}

export function createSettlement(
  groupId: string,
  payload: { to_user_id: string; amount: number },
): Promise<Settlement> {
  return api(`/expense-groups/${groupId}/settlements`, {
    method: "POST",
    json: payload,
  });
}

export function confirmSettlement(
  groupId: string,
  settlementId: string,
): Promise<Settlement> {
  return api(`/expense-groups/${groupId}/settlements/${settlementId}/confirm`, {
    method: "POST",
  });
}

// -------------------------------------------------------------------- format

export function fmtMoney(value: string | number): string {
  return Number(value).toLocaleString("vi-VN") + " ₫";
}

export function fmtPeriod(isoDate: string): string {
  const [y, m] = isoDate.split("-");
  return `${m}/${y}`;
}
