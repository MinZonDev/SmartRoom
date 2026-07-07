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

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

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
}

async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    body = new URLSearchParams(opts.form);
  }
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body,
  });

  if (res.status === 401 && !path.startsWith("/auth/login")) {
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
  },
): Promise<MeterReading> {
  return api(`/rooms/${roomId}/meter-readings`, { method: "PUT", json: payload });
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
