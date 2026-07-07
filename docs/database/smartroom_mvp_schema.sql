-- ============================================================================
-- SmartRoom - Database Schema (MVP)
-- Modules: (1) Quan ly cho thue (Landlord Management)
--          (2) Quan ly chi tieu & chia tien (Expense Splitting)
-- Target : PostgreSQL 14+
-- Note   : Mot User co the dong nhieu vai tro (landlord + tenant).
--          Vai tro duoc suy ra tu quan he du lieu; bang user_roles chi phuc
--          vu authorization (RBAC).
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto"; -- gen_random_uuid() cho PG < 13

-- ----------------------------------------------------------------------------
-- ENUM TYPES
-- ----------------------------------------------------------------------------
CREATE TYPE user_role           AS ENUM ('admin', 'landlord', 'tenant');
CREATE TYPE room_status         AS ENUM ('available', 'occupied', 'maintenance');
CREATE TYPE service_charge_type AS ENUM ('per_unit', 'per_person', 'per_room', 'flat');
CREATE TYPE contract_status     AS ENUM ('pending', 'active', 'expired', 'terminated');
CREATE TYPE invoice_status      AS ENUM ('draft', 'issued', 'partially_paid', 'paid', 'overdue', 'cancelled');
CREATE TYPE payment_method      AS ENUM ('cash', 'bank_transfer', 'e_wallet');
CREATE TYPE split_method        AS ENUM ('equal', 'ratio', 'exact');
CREATE TYPE settlement_status   AS ENUM ('pending', 'completed', 'cancelled');

-- ----------------------------------------------------------------------------
-- Trigger function: tu dong cap nhat updated_at
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 1. CORE: USERS & ROLES
-- ============================================================================

CREATE TABLE users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name      VARCHAR(120)  NOT NULL,
    email          VARCHAR(255)  NOT NULL UNIQUE,
    phone          VARCHAR(20)   UNIQUE,
    password_hash  VARCHAR(255)  NOT NULL,
    avatar_url     TEXT,
    is_active      BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ   NOT NULL DEFAULT now()
);
COMMENT ON TABLE users IS 'Danh tinh duy nhat. Vai tro (chu nha / khach thue) la ngu canh, khong gan cung vao user.';

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Role cap cho user de phan quyen (mot user co the co nhieu role dong thoi)
CREATE TABLE user_roles (
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        user_role   NOT NULL,
    granted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, role)
);

-- ============================================================================
-- 2. MODULE: QUAN LY CHO THUE (LANDLORD MANAGEMENT)
-- ============================================================================

-- Toa nha / khu tro thuoc so huu cua mot user (=> user do la landlord)
CREATE TABLE properties (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id    UUID          NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    name        VARCHAR(150)  NOT NULL,
    address     VARCHAR(255)  NOT NULL,
    city        VARCHAR(100),
    district    VARCHAR(100),
    description TEXT,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX idx_properties_owner ON properties(owner_id);
CREATE TRIGGER trg_properties_updated_at
    BEFORE UPDATE ON properties FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE rooms (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id   UUID          NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    code          VARCHAR(30)   NOT NULL,               -- vd: P101, A-202
    floor         SMALLINT,
    area_m2       NUMERIC(6,2)  CHECK (area_m2 > 0),
    base_price    NUMERIC(14,2) NOT NULL CHECK (base_price >= 0),
    max_occupants SMALLINT      NOT NULL DEFAULT 1 CHECK (max_occupants > 0),
    status        room_status   NOT NULL DEFAULT 'available',
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (property_id, code)
);
CREATE INDEX idx_rooms_property ON rooms(property_id);
CREATE TRIGGER trg_rooms_updated_at
    BEFORE UPDATE ON rooms FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Dich vu tinh phi cua tung toa nha: dien, nuoc, internet, rac, giu xe...
CREATE TABLE services (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id UUID                NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    name        VARCHAR(100)        NOT NULL,           -- vd: Dien, Nuoc
    unit        VARCHAR(20),                            -- vd: kWh, m3, thang
    unit_price  NUMERIC(14,2)       NOT NULL CHECK (unit_price >= 0),
    charge_type service_charge_type NOT NULL DEFAULT 'per_unit',
    is_active   BOOLEAN             NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ         NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ         NOT NULL DEFAULT now()
);
CREATE INDEX idx_services_property ON services(property_id);
CREATE TRIGGER trg_services_updated_at
    BEFORE UPDATE ON services FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Hop dong thue phong
CREATE TABLE contracts (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id        UUID            NOT NULL REFERENCES rooms(id) ON DELETE RESTRICT,
    code           VARCHAR(30)     NOT NULL UNIQUE,     -- vd: HD-2026-0001
    deposit_amount NUMERIC(14,2)   NOT NULL DEFAULT 0 CHECK (deposit_amount >= 0),
    monthly_rent   NUMERIC(14,2)   NOT NULL CHECK (monthly_rent >= 0),
    billing_day    SMALLINT        NOT NULL DEFAULT 1 CHECK (billing_day BETWEEN 1 AND 28),
    start_date     DATE            NOT NULL,
    end_date       DATE,
    status         contract_status NOT NULL DEFAULT 'pending',
    note           TEXT,
    created_at     TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ     NOT NULL DEFAULT now(),
    CHECK (end_date IS NULL OR end_date > start_date)
);
CREATE INDEX idx_contracts_room ON contracts(room_id);
-- Moi phong chi co toi da 1 hop dong dang hieu luc
CREATE UNIQUE INDEX uq_contracts_one_active_per_room
    ON contracts(room_id) WHERE status = 'active';
CREATE TRIGGER trg_contracts_updated_at
    BEFORE UPDATE ON contracts FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Nguoi o trong hop dong (ho tro ghep phong: N khach thue / 1 hop dong).
-- User xuat hien o day => dong vai tro TENANT (co the dong thoi la landlord noi khac).
CREATE TABLE contract_members (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id UUID        NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    is_primary  BOOLEAN     NOT NULL DEFAULT FALSE,     -- nguoi dai dien ky hop dong
    joined_at   DATE        NOT NULL DEFAULT CURRENT_DATE,
    left_at     DATE,
    UNIQUE (contract_id, user_id),
    CHECK (left_at IS NULL OR left_at >= joined_at)
);
CREATE INDEX idx_contract_members_user ON contract_members(user_id);
-- Moi hop dong chi co 1 nguoi dai dien
CREATE UNIQUE INDEX uq_contract_members_one_primary
    ON contract_members(contract_id) WHERE is_primary = TRUE;

-- Chi so cong to (dien / nuoc) theo ky - dau vao cho OCR o giai doan sau
CREATE TABLE meter_readings (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id        UUID          NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    service_id     UUID          NOT NULL REFERENCES services(id) ON DELETE RESTRICT,
    period         DATE          NOT NULL,              -- luon la ngay 01 cua thang, vd 2026-07-01
    previous_value NUMERIC(12,2) NOT NULL CHECK (previous_value >= 0),
    current_value  NUMERIC(12,2) NOT NULL,
    reading_date   DATE          NOT NULL DEFAULT CURRENT_DATE,
    image_url      TEXT,                                -- anh chup cong to (phuc vu OCR)
    created_by     UUID          REFERENCES users(id) ON DELETE SET NULL,
    created_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (room_id, service_id, period),
    CHECK (current_value >= previous_value)
);
CREATE INDEX idx_meter_readings_room ON meter_readings(room_id);

-- ============================================================================
-- 3. MODULE: HOA DON & THANH TOAN (BILLING)
-- ============================================================================

CREATE TABLE invoices (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id  UUID           NOT NULL REFERENCES contracts(id) ON DELETE RESTRICT,
    code         VARCHAR(30)    NOT NULL UNIQUE,        -- vd: INV-2026-07-0001
    period       DATE           NOT NULL,               -- ky hoa don (ngay 01 cua thang)
    due_date     DATE           NOT NULL,
    total_amount NUMERIC(14,2)  NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    paid_amount  NUMERIC(14,2)  NOT NULL DEFAULT 0 CHECK (paid_amount >= 0),
    status       invoice_status NOT NULL DEFAULT 'draft',
    issued_at    TIMESTAMPTZ,
    pdf_url      TEXT,                                  -- link S3 file PDF do worker sinh ra
    note         TEXT,
    created_at   TIMESTAMPTZ    NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ    NOT NULL DEFAULT now(),
    UNIQUE (contract_id, period)                        -- 1 hoa don / hop dong / thang
);
CREATE INDEX idx_invoices_contract ON invoices(contract_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE TRIGGER trg_invoices_updated_at
    BEFORE UPDATE ON invoices FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Dong chi tiet: tien phong, dien, nuoc, rac... (moi dong 1 khoan)
CREATE TABLE invoice_items (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id  UUID          NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    service_id  UUID          REFERENCES services(id) ON DELETE SET NULL, -- NULL = tien phong / khoan tuy chinh
    description VARCHAR(255)  NOT NULL,
    quantity    NUMERIC(12,2) NOT NULL DEFAULT 1 CHECK (quantity >= 0),
    unit_price  NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (unit_price >= 0),
    amount      NUMERIC(14,2) NOT NULL CHECK (amount >= 0)
);
CREATE INDEX idx_invoice_items_invoice ON invoice_items(invoice_id);

CREATE TABLE payments (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID           NOT NULL REFERENCES invoices(id) ON DELETE RESTRICT,
    payer_id   UUID           REFERENCES users(id) ON DELETE SET NULL,
    amount     NUMERIC(14,2)  NOT NULL CHECK (amount > 0),
    method     payment_method NOT NULL DEFAULT 'bank_transfer',
    paid_at    TIMESTAMPTZ    NOT NULL DEFAULT now(),
    note       TEXT,
    created_at TIMESTAMPTZ    NOT NULL DEFAULT now()
);
CREATE INDEX idx_payments_invoice ON payments(invoice_id);

-- ============================================================================
-- 4. MODULE: CHIA TIEN CHI TIEU (EXPENSE SPLITTING - mo hinh Splitwise)
-- ============================================================================

-- Nhom chia tien: thuong gan voi 1 phong (roommates), nhung cung co the
-- la nhom tu do (room_id NULL) - vd nhom ban be di choi chung.
CREATE TABLE expense_groups (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id    UUID         REFERENCES rooms(id) ON DELETE SET NULL,
    name       VARCHAR(120) NOT NULL,
    created_by UUID         NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_expense_groups_room ON expense_groups(room_id);

CREATE TABLE expense_group_members (
    group_id  UUID        NOT NULL REFERENCES expense_groups(id) ON DELETE CASCADE,
    user_id   UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    left_at   TIMESTAMPTZ,
    PRIMARY KEY (group_id, user_id)
);
CREATE INDEX idx_expense_group_members_user ON expense_group_members(user_id);

-- Mot khoan chi: payer_id la nguoi da tra tien ho ca nhom
CREATE TABLE expenses (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id          UUID          NOT NULL REFERENCES expense_groups(id) ON DELETE CASCADE,
    payer_id          UUID          NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    title             VARCHAR(150)  NOT NULL,
    amount            NUMERIC(14,2) NOT NULL CHECK (amount > 0),
    expense_date      DATE          NOT NULL DEFAULT CURRENT_DATE,
    split_method      split_method  NOT NULL DEFAULT 'equal',
    receipt_image_url TEXT,                              -- anh hoa don (dau vao OCR giai doan sau)
    note              TEXT,
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX idx_expenses_group ON expenses(group_id);
CREATE INDEX idx_expenses_payer ON expenses(payer_id);

-- Phan moi thanh vien phai chiu cho tung khoan chi.
-- Rang buoc nghiep vu SUM(share_amount) = expenses.amount xu ly o service layer.
CREATE TABLE expense_shares (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expense_id   UUID          NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
    user_id      UUID          NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    share_amount NUMERIC(14,2) NOT NULL CHECK (share_amount >= 0),
    UNIQUE (expense_id, user_id)
);
CREATE INDEX idx_expense_shares_user ON expense_shares(user_id);

-- Giao dich bu tru cong no giua 2 thanh vien trong nhom
CREATE TABLE settlements (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id     UUID              NOT NULL REFERENCES expense_groups(id) ON DELETE CASCADE,
    from_user_id UUID              NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    to_user_id   UUID              NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    amount       NUMERIC(14,2)     NOT NULL CHECK (amount > 0),
    status       settlement_status NOT NULL DEFAULT 'pending',
    settled_at   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ       NOT NULL DEFAULT now(),
    CHECK (from_user_id <> to_user_id)
);
CREATE INDEX idx_settlements_group ON settlements(group_id);
CREATE INDEX idx_settlements_from_user ON settlements(from_user_id);
CREATE INDEX idx_settlements_to_user ON settlements(to_user_id);
