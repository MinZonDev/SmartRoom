"""Python enums ánh xạ 1-1 với các ENUM type trong PostgreSQL."""

from enum import Enum


class RoomStatus(str, Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"


class ServiceChargeType(str, Enum):
    PER_UNIT = "per_unit"      # theo chỉ số công tơ (điện, nước)
    PER_PERSON = "per_person"  # theo đầu người (rác, nước khoán)
    PER_ROOM = "per_room"      # theo phòng (internet)
    FLAT = "flat"              # phí cố định


class ContractStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class PaymentMethod(str, Enum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    E_WALLET = "e_wallet"


class SplitMethod(str, Enum):
    EQUAL = "equal"   # chia đều
    RATIO = "ratio"   # theo trọng số
    EXACT = "exact"   # số tiền cụ thể từng người


class SettlementStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
