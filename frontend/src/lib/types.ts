/**
 * Types ánh xạ 1-1 với Pydantic schemas của backend.
 * Lưu ý: các trường tiền (Decimal) được backend serialize thành STRING.
 */

export interface User {
  id: string;
  full_name: string;
  email: string;
  phone: string | null;
  avatar_url: string | null;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface Property {
  id: string;
  owner_id: string;
  name: string;
  address: string;
  city: string | null;
  district: string | null;
  description: string | null;
}

export type RoomStatus = "available" | "occupied" | "maintenance";

export interface Room {
  id: string;
  property_id: string;
  code: string;
  floor: number | null;
  area_m2: string | null;
  base_price: string;
  max_occupants: number;
  status: RoomStatus;
}

export type ChargeType = "per_unit" | "per_person" | "per_room" | "flat";

export interface UtilityService {
  id: string;
  property_id: string;
  name: string;
  unit: string | null;
  unit_price: string;
  charge_type: ChargeType;
  is_active: boolean;
}

export interface MeterReading {
  id: string;
  room_id: string;
  service_id: string;
  period: string;
  previous_value: string;
  current_value: string;
  reading_date: string;
  image_url: string | null;
}

export type ContractStatus = "pending" | "active" | "expired" | "terminated";

export interface ContractMember {
  id: string;
  user_id: string;
  is_primary: boolean;
  joined_at: string;
  left_at: string | null;
}

export interface Contract {
  id: string;
  room_id: string;
  code: string;
  deposit_amount: string;
  monthly_rent: string;
  billing_day: number;
  start_date: string;
  end_date: string | null;
  status: ContractStatus;
  note: string | null;
  members: ContractMember[];
}

export type InvoiceStatus =
  | "draft"
  | "issued"
  | "partially_paid"
  | "paid"
  | "overdue"
  | "cancelled";

export interface InvoiceItem {
  description: string;
  quantity: string;
  unit_price: string;
  amount: string;
}

export interface Invoice {
  id: string;
  contract_id: string;
  code: string;
  period: string;
  due_date: string;
  total_amount: string;
  paid_amount: string;
  status: InvoiceStatus;
  issued_at: string | null;
  pdf_url: string | null;
  items: InvoiceItem[];
}

export type JobStatus = "pending" | "processing" | "completed" | "failed";

export interface BillingJob {
  job_id: string;
  status: JobStatus;
  meta: Record<string, unknown>;
  result: {
    invoices_created: number;
    skipped: string[];
    errors: string[];
  } | null;
  error: string | null;
}

export interface CloseMonthAccepted {
  job_id: string;
  status: JobStatus;
  status_url: string;
}

// ------------------------------------------------------------------ expenses

export interface UserBrief {
  id: string;
  full_name: string;
}

export interface GroupMember {
  user: UserBrief;
  joined_at: string;
  left_at: string | null;
}

export interface ExpenseGroup {
  id: string;
  name: string;
  created_by: string;
  created_at: string;
  members: GroupMember[];
}

export type SplitMethod = "equal" | "ratio" | "exact";

export interface ExpenseShare {
  user_id: string;
  share_amount: string;
}

export interface Expense {
  id: string;
  group_id: string;
  payer_id: string;
  title: string;
  amount: string;
  expense_date: string;
  split_method: SplitMethod;
  receipt_image_url: string | null;
  note: string | null;
  created_at: string;
  shares: ExpenseShare[];
}

export interface BalanceEntry {
  user_id: string;
  full_name: string;
  balance: string;
}

export interface SettlementSuggestion {
  from_user_id: string;
  from_name: string;
  to_user_id: string;
  to_name: string;
  amount: string;
}

export type SettlementStatus = "pending" | "completed" | "cancelled";

export interface Settlement {
  id: string;
  group_id: string;
  from_user_id: string;
  to_user_id: string;
  amount: string;
  status: SettlementStatus;
  settled_at: string | null;
  created_at: string;
}
