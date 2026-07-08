# SmartRoom — Nhật ký dự án & Tiến độ

> Nền tảng quản lý không gian sống, nhà trọ và ghép phòng tích hợp AI.
> **File này là NGUỒN SỰ THẬT về tiến độ** — mọi session (người hoặc AI) bắt đầu bằng việc đọc file này, làm xong việc gì phải cập nhật ngay vào đây.

## 🗺️ Roadmap hoàn thiện (kế hoạch đang chạy — 2026-07-07)

| # | Hạng mục | Trạng thái |
|---|---|---|
| A | Git init + .gitignore + README + commit đầu tiên | ✅ commit `2f5ec6d` (102 files; đã gỡ repo git con do create-next-app tạo trong frontend/, .gitattributes ép LF cho *.sh) |
| B | Bộ test pytest cho logic thuần (chia tiền, matching, OCR, security) | ✅ 30/30 pass — `backend/tests/`, chạy: `python -m pytest -q` (đã refactor `compute_shares` thành hàm thuần) |
| C | Presigned URL tải PDF hóa đơn (backend + nút trên FE) | ✅ test thật: tải PDF 2133 bytes từ LocalStack, landlord khác bị 404 |
| D | Commit mốc 2 (tests + presigned URL) | ✅ commit `8bbbae0` |
| E1 | Refresh token (rotation) + rate-limit login bằng Redis | ✅ test thật: refresh ra cặp mới, access-làm-refresh bị 401, login sai 401×5→429 |
| E2 | Trang tenant: khách thuê xem + tải PDF hóa đơn của mình | ✅ test thật: tenant thấy 1 hóa đơn, tải PDF 200, tenant ngoài hợp đồng 404 |
| E3 | CI GitHub Actions (pytest + npm build) | ✅ **verify chạy thật trên GitHub: xanh** (sau fix `asyncpg` thiếu trong requirements-ci — commit `700b124`) |
| E4 | Commit mốc 3 | ✅ commit `f7c9553` |
| F0 | Push GitHub `https://github.com/MinZonDev/SmartRoom` | ✅ remote origin, branch main |
| F1 | Luồng OCR hoàn chỉnh: upload ảnh → đọc số → confirm → meter_readings kèm ảnh S3 | ✅ **test OCR THẬT**: đọc "01315"/"00842" chính xác 100%, confidence ≥0.9999, warm 2.4s/request |
| F2a | Integration tests với Postgres thật (billing/contracts/expenses) + postgres service trong CI | ✅ 6 tests — tổng 43→46 pass |
| F2b | Logout + thu hồi refresh token (Redis denylist, refresh dùng-một-lần) | ✅ test thật: dùng lại refresh cũ 401, refresh sau logout 401 |
| F2c | Commit mốc 5 + CI xanh | ✅ commit `2584bdb` — CI xanh, integration tests chạy trên GitHub với postgres service |
| G1 | Terraform: SQS + DLQ + S3 + SES (verify bằng apply vào LocalStack) | ✅ apply 6 resources OK rồi destroy sạch (`infra/terraform/`) |
| G2 | Notification email khi phát hành hóa đơn (SES, event-driven sau worker) | ✅ e2e thật: 3 email đúng người đúng hóa đơn qua LocalStack SES |
| G3 | Đổi mật khẩu + tự cấp role landlord khi tạo property đầu tiên | ✅ e2e: sai mật khẩu 401, đổi xong login cũ 401/mới OK; user_roles có landlord, idempotent |
| G4 | Commit mốc 6 + CI xanh | 🔄 đang chờ CI |
| H | *Session sau:* deploy AWS thật (cần credentials), quên mật khẩu (cần email thật), OCR crop ROI với ảnh đồng hồ thật | ⬜ backlog |

*Cập nhật bảng này ngay khi chuyển trạng thái: 🔄 đang làm / ✅ xong / ⬜ chưa.*

## Tech Stack

- **Backend**: Python FastAPI + SQLAlchemy 2.0 (async) | **DB**: PostgreSQL + Redis
- **Frontend**: Next.js 16 (TypeScript) + TailwindCSS v4 — `frontend/`
- **AI/ML**: Scikit-learn (recommender), EasyOCR/Tesseract (OCR) *(chưa bắt đầu)*
- **Infra**: AWS — EC2, S3, SQS, Lambda | Kiến trúc: **Modular Monolith**, event-driven

---

## ✅ Đã hoàn thành

### 2026-07-07 — Thiết kế Database MVP
- ERD cho 2 module MVP: **Quản lý cho thuê** + **Chia tiền chi tiêu** (16 bảng, 8 ENUM types).
- File: `docs/database/smartroom_mvp_schema.sql` (DDL đầy đủ: constraints, indexes, trigger updated_at).
- File: `docs/database/smartroom_mvp_erd.drawio` (XML uncompressed — mở trực tiếp trong draw.io).
- Quyết định chính:
  - User **trung lập vai trò** — landlord/tenant suy ra từ quan hệ; `user_roles` chỉ cho RBAC.
  - UUID PK, `NUMERIC(14,2)` cho tiền, partial index "1 phòng chỉ 1 hợp đồng active".
  - Chia tiền theo mô hình Splitwise: `expenses` → `expense_shares` → `settlements`.

### 2026-07-07 — Backend skeleton + Luồng "Chốt tháng" (event-driven)
- Scaffold **Modular Monolith** trong `backend/` (cấu trúc bên dưới).
- Luồng tạo hóa đơn hàng tháng **không block API**:
  1. `POST /api/v1/billing/close-month` → validate quyền sở hữu → tạo `job_id` (Redis) → publish message vào **SQS** → trả **202 Accepted**.
  2. **Worker** (`python -m app.workers.billing_worker`) long-poll SQS → tính tiền phòng + dịch vụ (per_unit theo chỉ số công tơ / per_person / per_room / flat) → sinh **PDF** (reportlab, chạy trong thread) → upload **S3** → cập nhật `pdf_url`.
  3. Frontend poll `GET /api/v1/billing/jobs/{job_id}` xem tiến độ (Redis, TTL 24h).
- Tính chất quan trọng:
  - **Idempotent**: `UNIQUE(contract_id, period)` + check tồn tại → SQS at-least-once không tạo hóa đơn trùng.
  - Thất bại → message ở lại queue → retry → quá maxReceiveCount vào **DLQ** (cấu hình hạ tầng).
  - Thiếu chỉ số công tơ 1 phòng chỉ ghi vào `errors`, không chặn cả tòa nhà.
- **Thay đổi schema**: thêm cột `invoices.pdf_url TEXT` (đã cập nhật file .sql; DB đang chạy thì `ALTER TABLE invoices ADD COLUMN pdf_url TEXT;`).

### 2026-07-07 — Module Smart OCR (đọc chỉ số đồng hồ điện/nước)
- `POST /api/v1/ocr/meter-reading`: upload ảnh (jpeg/png/webp, ≤8MB) → trả chỉ số + confidence + danh sách candidates.
- Kiến trúc tối ưu memory/startup:
  - **Lazy singleton** `MeterOCREngine` — `import easyocr` nằm trong `load()`, torch không chiếm RAM ở process không dùng OCR; double-checked locking chống nạp trùng model.
  - **Warm-up không chặn startup**: lifespan bắn `asyncio.create_task(to_thread(engine.load))` — server nhận request ngay, model nạp song song. `GET /api/v1/ocr/health` là readiness probe riêng.
  - **Inference qua `asyncio.to_thread` + `Semaphore(2)`** (config `OCR_MAX_CONCURRENCY`) — không block event loop, không nghẽn CPU.
  - Preprocessing OpenCV: resize ≤1280px, grayscale, CLAHE tăng tương phản (đồng hồ trong hộp kỹ thuật thiếu sáng).
  - Chọn kết quả: allowlist chữ số, lọc 3-9 ký tự, score = confidence + 0.03×độ dài; `needs_confirmation=true` khi confidence < 0.55.
- **Human-in-the-loop**: OCR chỉ gợi ý — user xác nhận rồi client mới ghi `meter_readings` (OCR không tự ghi DB).
- Engine không phụ thuộc FastAPI → tái sử dụng nguyên vẹn trong SQS worker / microservice OCR riêng khi cần scale.
- Config mới: `OCR_GPU`, `OCR_MODEL_DIR` (bake weights vào Docker image), `OCR_MAX_CONCURRENCY`, `OCR_MAX_IMAGE_MB`.

### 2026-07-07 — Engine Ghép phòng thông minh (Roommate Matching)
- `app/modules/matching/` — engine thuần (numpy + scikit-learn), chưa có router/DB, đã chạy thử OK với mock data.
- Thuật toán **Filter-then-Rank** (kiến trúc recommender 2 tầng):
  1. **Hard filters 2 chiều**: hút thuốc / thú cưng là deal-breaker loại trừ (A chấp nhận B VÀ B chấp nhận A), không đưa vào điểm số.
  2. **Weighted Cosine Similarity**: MinMax scaling về `[0.1, 1]` (tránh zero vector) → nhân `√w` từng feature (giờ ngủ w=2.0, sạch sẽ w=1.8... trong `DEFAULT_FEATURE_WEIGHTS`) → `cosine_similarity` → top K.
- Vector 9 features: `bedtime_hour, tidiness, noise_tolerance, cooking_per_week, guests_per_month, work_from_home, is_smoker, has_pet, budget_vnd`.
- Demo: `PYTHONUTF8=1 python -m app.modules.matching.mock_data` — 8 persona kiểm chứng: người giống hệt đứng top 1, người hút thuốc bị loại khỏi kết quả.
- Content-based vì cold start (chưa có dữ liệu tương tác); backlog: học trọng số từ feedback match thành công.

### 2026-07-07 — docker-compose + Alembic + chạy end-to-end THÀNH CÔNG ✅
- **docker-compose.yml** (root): `postgres:16` (host port **5434**), `redis:7` (host port **6380**, tên `smartroom-redis-cache`), `localstack:3` (SQS+S3, port 4566) — port/tên lệch chuẩn vì máy còn container của dự án cũ *finding-rooms* (`smartroom-db` chiếm 5433, `smartroom-redis` chiếm 6379, `backend-db-1` chiếm 5432). Profile `app` để chạy cả API+worker trong container (`docker compose --profile app up`).
- **infra/localstack/init-aws.sh**: tự tạo queue `smartroom-billing` + DLQ (maxReceiveCount=3) + bucket khi LocalStack khởi động. **Lưu ý**: script phải `export AWS_DEFAULT_REGION=ap-southeast-1` khớp với `.env` — SQS scope theo region, lệch là `QueueDoesNotExist`.
- **Alembic**: `env.py` async (URL đọc từ Settings), `include_object` bỏ qua bảng chưa có ORM model; migration `0001` nhúng schema SQL đầy đủ (autogenerate không làm được trigger/partial index/plpgsql). **`alembic.ini` phải giữ ASCII-only** (configparser đọc cp1252 trên Windows).
- **scripts/seed_demo.py**: 1 chủ nhà + 2 khách thuê, 2 phòng (P102 ghép 2 người), 4 dịch vụ đủ 4 charge_type, chỉ số điện kỳ 2026-07. Idempotent.
- **Kết quả test e2e thật** (POST close-month → SQS → worker → PDF → S3):
  - 2 hóa đơn đúng từng đồng: P101 = 4.182.500đ (phòng 3.5tr + điện 115kWh×3.5k + nước 1 người + internet + rác); P102 = 5.147.000đ (nước ×2 người ✓)
  - PDF upload S3 thành công, `pdf_url` gán vào invoice ✓
  - Chốt tháng lần 2: `invoices_created=0`, skip cả 2 — idempotent ✓
- **Bug đã fix trong lúc test**: `InvoiceGenerationService._get_active_contracts` thiếu `selectinload(Contract.room)` → worker nổ `greenlet_spawn has not been called` khi `_attach_pdf` đọc `contract.room.code` (lazy load trong async session). Bài học: **mọi relationship truy cập sau query phải eager-load**.
- Refactor: `shared/aws.py` — factory boto3 client duy nhất, truyền credentials tường minh từ Settings (LocalStack cần `test/test`; production để trống → IAM role).

### 2026-07-07 — Module Auth JWT (thay stub X-User-Id) ✅
- **Stack**: PyJWT + bcrypt trực tiếp (né `python-jose`/`passlib` — ngừng bảo trì, có CVE). Access token HS256, TTL 60' (config `JWT_SECRET_KEY`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`).
- Endpoints: `POST /auth/register` (201/409), `POST /auth/login` (OAuth2 password form, username=email — Swagger có nút Authorize), `GET /auth/me`.
- `core/dependencies.get_current_user_id` đổi ruột header→JWT — **billing/OCR router không sửa dòng nào**. Endpoint cần profile/chặn user bị khóa dùng `auth/dependencies.get_current_user` (có query DB).
- Bảo mật: bcrypt chạy qua `asyncio.to_thread` (CPU-bound ~200ms); **chống timing attack** — email không tồn tại vẫn verify dummy hash; login sai luôn trả một message chung.
- Seed cập nhật: mọi user demo có mật khẩu `smartroom123` (idempotent — chạy lại tự đồng bộ hash cũ).
- **Đã test e2e**: no-token→401, sai mật khẩu→401, login→token→/me, close-month bằng Bearer token→202→worker completed, register 201, email trùng→409.
- ⚠️ Lưu ý test bằng curl trong Git Bash trên Windows: body JSON có tiếng Việt phải gửi qua `--data-binary @file` (inline `-d` bị mangle UTF-8 → lỗi 400 "error parsing the body" giả).

### 2026-07-07 — CRUD Properties + Contracts (state machine) ✅
- **Properties** (`modules/properties/`): CRUD tòa nhà, phòng (unique code/property → 409), dịch vụ (xóa cứng bị chặn khi có tham chiếu — khuyến nghị PATCH `is_active=false`), **upsert chỉ số công tơ** theo (room, service, period) qua `PUT /rooms/{id}/meter-readings`.
- **Contracts** (`modules/contracts/`): tạo hợp đồng ở `pending` (validate: đúng 1 người đại diện, ≤ max_occupants, users tồn tại, tự sinh mã `HD-YYYY-XXXXXX`) → `POST /{id}/activate` (check 1-active-per-room, phòng → `occupied`) → `POST /{id}/terminate` (đóng `left_at` members, phòng → `available`). PATCH điều khoản chỉ khi `pending`. Member rời phòng = set `left_at` (giữ lịch sử cho per_person), người đại diện không rời được.
- **Authorization theo resource**: mọi query JOIN lọc `owner_id` ngay trong SQL; "không tồn tại" và "không có quyền" trả cùng 404 (không lộ thông tin). `ConflictError` mới → handler 409.
- **Đã test e2e toàn trình bằng API thật** (landlord2 tự dựng từ đầu không cần seed): register → property → rooms (dup code 409) → services → meter reading → contract → activate (lần 2: 409; phòng occupied) → **close-month ra hóa đơn 3.310.000đ đúng từng đồng** (3tr + 80kWh×3.5k + 30k rác) → add member (member 3: 409 max_occupants) → remove member (primary: 409) → terminate (phòng available) → landlord khác truy cập: 404.

### 2026-07-07 — Module Expenses (chia tiền — mô hình Splitwise) ✅
- **Nhóm chi tiêu**: tạo nhóm (người tạo tự là thành viên), thêm member (rejoin mở lại membership cũ), authorization theo **membership** — người ngoài nhóm nhận 404.
- **Khoản chi 3 kiểu chia** (`POST /expense-groups/{id}/expenses`): `equal` (mặc định mọi thành viên đang ở), `ratio` (theo weight), `exact` (schema validate `SUM == amount` → 422 nếu lệch). Xóa khoản chi: chỉ người trả.
- **Bất biến `SUM(shares) = amount`**: chia `ROUND_DOWN` từng phần + phát phần dư 0.01/người từ đầu danh sách — đã test 100k/3 người = 33.333,34 + 33.333,33×2, tổng khớp tuyệt đối.
- **Số dư là dữ liệu dẫn xuất** (không lưu): `balance = Σtrả − Σchịu + Σsettlement gửi − Σnhận` (chỉ tính completed, gồm cả member đã rời vì có thể còn nợ cũ).
- **Gợi ý trả nợ**: greedy min-cash-flow (ghép nợ lớn nhất ↔ được nhận lớn nhất) → số giao dịch tối thiểu.
- **Settlement 2 bên**: người trả tạo `pending` → chỉ **người nhận** confirm → `completed` (pending chưa tính vào số dư); 2 bên đều hủy được khi pending.
- **Đã test e2e** (3 tenant qua API thật): 3 kiểu chia → số dư khớp tính tay (A +90k, B −30k, C −60k, tổng = 0) → gợi ý đúng 2 giao dịch tối thiểu → B trả A 30k, C confirm hộ bị 403, A confirm xong B về 0 → exact lệch tổng 422 → người ngoài nhóm 404.

### 2026-07-07 — Frontend Next.js (MVP UI) ✅
- **Stack**: Next.js 16 (App Router, Turbopack) + React 19 + TypeScript + Tailwind v4, scaffold bằng create-next-app trong `frontend/`.
- **Kiến trúc FE**: client components + API client tập trung (`src/lib/api.ts` — fetch wrapper, JWT localStorage, 401 tự về /login); types ánh xạ 1-1 Pydantic schemas (`src/lib/types.ts` — **lưu ý: Decimal từ backend là string trong JSON**); UI primitives tự viết không kéo component library (`src/components/ui.tsx`).
- **Pages**: `/login`, `/register` → `/dashboard` (danh sách + tạo nhà trọ) → `/properties/[id]` (4 tab: Phòng + ghi chỉ số công tơ, Dịch vụ, Hợp đồng kích hoạt/chấm dứt, Hóa đơn + nút **Chốt tháng** poll job 1.5s/lần tới khi completed) → `/expenses` + `/expenses/[id]` (số dư màu xanh/đỏ, gợi ý trả nợ với nút "Tôi đã trả" chỉ hiện cho đúng người nợ, xác nhận settlement chỉ hiện cho người nhận).
- **Backend bổ sung cho FE**: CORS middleware (localhost:3000 + **3001**), `GET /billing/invoices?property_id=`, `GET /auth/users/lookup?email=` (FE nhập email thay vì UUID khi thêm người vào hợp đồng/nhóm).
- Đã verify: `npm run build` sạch (typecheck + 8 routes), dev server render mọi page 200, CORS preflight OK.
- ⚠️ **Port 3000 bị Grafana của dự án cũ chiếm** → Next dev tự nhảy sang **3001** (CORS đã cover cả 2). Dọn container cũ thì về 3000.

### 2026-07-07 — Hoàn thiện đợt 1: Git + Tests + Presigned URL ✅
- **Git**: repo khởi tạo tại root, branch `main`. Commit `2f5ec6d` (MVP 102 files) + commit mốc 2. Lưu ý đã xử lý: create-next-app tự tạo repo git con trong `frontend/` (đã gỡ `frontend/.git`); `.gitattributes` ép **LF cho `*.sh`** — nếu không script LocalStack init sẽ chết vì CRLF.
- **Tests**: `backend/tests/` — 30 tests pass (`python -m pytest -q`, cần `pip install -r requirements-dev.txt`):
  - `test_expense_split.py`: bất biến SUM(shares)==amount cho cả 3 kiểu chia + làm tròn + schema validation
  - `test_matching.py`: hard filter loại người hút thuốc, không tự match chính mình, ranking đúng
  - `test_ocr_service.py`: FakeEngine (không cần torch) — chọn best candidate, loại serial dài, needs_confirmation
  - `test_auth_security.py`: bcrypt roundtrip + dummy hash, JWT giả mạo/sai secret/sai type bị từ chối
  - Refactor kèm theo: `compute_shares` từ method → hàm thuần module-level (testable không cần DB)
  - *Chưa có*: integration tests với DB (testcontainers) — backlog
- **Presigned URL PDF**: `GET /billing/invoices/{id}/pdf-url` → URL S3 có chữ ký, hết hạn 15 phút (bucket không bao giờ public). FE: nút "Tải PDF" trong tab Hóa đơn xin URL mới mỗi lần bấm. `S3Storage` thêm `presigned_url()` + `key_from_uri()`.

### 2026-07-07 — Hoàn thiện đợt 2: Refresh token + Trang tenant + CI ✅
- **Refresh token (rotation)**: `POST /auth/refresh` — refresh TTL 14 ngày (`JWT_REFRESH_TOKEN_EXPIRE_DAYS`), mỗi lần refresh cấp cặp mới. Token có claim `type` (access/refresh) — dùng chéo bị 401. *Stateless — chưa có revocation list (backlog: Redis denylist khi logout).* FE: lưu cả 2 token, **tự refresh khi gặp 401 rồi retry request gốc** (nhiều request 401 đồng thời chỉ refresh 1 lần — `refreshInFlight` guard trong `api.ts`).
- **Rate-limit login**: `FixedWindowRateLimiter` (Redis INCR+EXPIRE, `app/shared/rate_limit.py`) — 5 lần/60s theo email → 429. Config: `LOGIN_RATE_LIMIT_ATTEMPTS/WINDOW_SECONDS`. Test thật: 401×5 rồi 429.
- **Trang tenant**: `GET /billing/my-invoices` (hóa đơn mọi hợp đồng user là thành viên) + pdf-url mở quyền cho **chủ nhà HOẶC thành viên hợp đồng** (`get_invoice_for_user` — outerjoin contract_members). FE: trang `/my-invoices` + mục nav "Hóa đơn của tôi". Test thật: tenant C thấy đúng 1 hóa đơn, tải PDF 200; tenant B ngoài hợp đồng bị 404.
- **CI**: `.github/workflows/ci.yml` — 2 jobs: pytest (dùng `backend/requirements-ci.txt` — bộ nhẹ KHÔNG có easyocr/torch, tests OCR dùng FakeEngine) + npm build. Chưa verify chạy thật (cần push GitHub).
- **Tests**: 37 pass (thêm `test_rate_limit.py` với FakeRedis + 3 test refresh token).
- Refactor nhỏ: `_redis_client` → `get_redis_client` (public, auth router dùng cho limiter).

### 2026-07-07 — Hoàn thiện đợt 3: Push GitHub + CI xanh + Smart OCR chạy thật ✅
- **GitHub**: push lên `https://github.com/MinZonDev/SmartRoom` (remote `origin`, branch `main`).
- **CI verify thật**: run đầu FAIL vì `requirements-ci.txt` thiếu `asyncpg` (bài học: `app/core/database.py` tạo async engine **ngay lúc import** nên driver cần cả khi unit test không đụng DB — đã tái hiện chính xác bằng venv sạch trước khi fix). Run 2 (commit `700b124`): **cả 2 jobs xanh**.
- **Luồng Smart OCR end-to-end** (dev machine đã cài easyocr + torch 2.12 CPU):
  1. `POST /ocr/meter-reading`: đọc số + **upload ảnh gốc lên S3** (`meter-images/{uuid}.jpg`) → trả `image_url` (làm bằng chứng khi tranh chấp chỉ số).
  2. User xác nhận → `PUT /rooms/{id}/meter-readings` kèm `image_url` (schema mới có field này; update không gửi ảnh thì **giữ ảnh cũ** — `exclude_none`).
  3. FE: nút "📷 Đọc từ ảnh" trong form ghi chỉ số — OCR tự điền số, hiện cảnh báo khi `needs_confirmation`.
- **Kết quả test OCR thật** (ảnh đồng hồ giả lập bằng cv2): "01315"→1315 confidence 1.0; "00842"→842 confidence 0.9999. Cold start (tải model ~150MB + nạp): 2m37s; **warm: 2.4s/request**. `/ocr/health` phản ánh đúng trạng thái warm-up.
- Lưu ý vận hành: process API đang chạy vẫn dùng được easyocr cài sau đó (import lazy trong `load()`) — không cần restart.

### 2026-07-08 — Hoàn thiện đợt 4: Integration tests + Token revocation ✅
- **Integration tests** (`tests/integration/`, marker `integration`, tự skip nếu không có Postgres):
  - `test_billing_flow.py`: hóa đơn đúng từng đồng (3.660.000đ với đủ 4 charge_type + 2 người), idempotency, thiếu chỉ số ghi lỗi không chặn
  - `test_contract_state.py`: vòng đời activate→terminate đầy đủ + **partial unique index chặn 2 active/phòng khi bypass service** (ghi thẳng SQL)
  - `test_expense_balances.py`: bất biến tổng số dư = 0, settlement pending không tính, confirm xong về 0
  - Fixture: mỗi test nhận schema sạch (drop_all/create_all, function-scoped tránh lỗi event-loop); `TEST_DATABASE_URL` (local mặc định :5434/smartroom_test); dùng pytest-asyncio (`asyncio_mode=auto`)
  - **ORM bổ sung 2 partial unique indexes** vào models (parity với DB) để create_all trong test DB có đúng ràng buộc
  - CI: job backend-tests thêm **postgres service** — chạy cả integration tests
- **Token revocation** (`auth/denylist.py` — Redis, TTL = thời gian sống còn lại của token):
  - Token có claim `jti`; **refresh dùng-một-lần**: rotation tự thu hồi token vừa dùng — token bị đánh cắp dùng lại là 401
  - `POST /auth/logout`: thu hồi refresh token (idempotent — token rác vẫn 204); FE nút Đăng xuất gọi API thật rồi mới xóa local
  - ⚠️ Session đăng nhập trước update này không có `jti` → refresh bị 401, phải login lại (một lần duy nhất)
  - Access token vẫn stateless (sống tối đa 60') — trade-off chấp nhận được
- Tests: **46 pass** (40 unit + 6 integration). E2E curl: refresh cũ → 401 ✓, refresh sau logout → 401 ✓.

### 2026-07-08 — Hoàn thiện đợt 5: Terraform + Email notification + Auth bổ sung ✅
- **Terraform** (`infra/terraform/`): SQS billing + DLQ (redrive maxReceiveCount=3, visibility 120s, long-poll 20s) + S3 (block public access + SSE-AES256, chỉ truy cập qua presigned URL) + SES sender identity. Biến `use_localstack=true` trỏ provider về :4566 (kèm `s3_use_path_style` — không có thì lỗi DNS `bucket.localhost`). **Đã verify: apply 6 resources vào LocalStack rồi destroy sạch.** Production: `terraform apply` không var (cần AWS credentials). State đã gitignore.
- **Email notification** (`shared/email.py` + `billing/notifications.py`): worker sau khi sinh hóa đơn gửi email cho mọi thành viên đang ở của từng hợp đồng (subject + body tiếng Việt, tổng tiền, hạn thanh toán). **Best-effort**: email lỗi chỉ log không fail job. LocalStack cần `SERVICES: sqs,s3,ses` (đã sửa compose — **đổi SERVICES phải recreate container**) + verify sender trong init script. **e2e thật**: chốt tháng 2026-08 → 3 email đúng người (tenant ở 2 phòng nhận 2 email). Xem email đã gửi: `curl localhost:4566/_aws/ses` (LocalStack v3 — KHÔNG phải `/_localstack/ses`).
- **Auth bổ sung**: `POST /auth/change-password` (yêu cầu mật khẩu hiện tại, bcrypt trong thread); tạo property đầu tiên tự cấp role `landlord` vào `user_roles` (pg `ON CONFLICT DO NOTHING` — idempotent, model `UserRoleAssignment` mới).
- Tests: **48 pass** (+2 integration: notification gửi đúng thành viên, landlord role idempotent).
- Terraform binary tải về scratchpad (không cài hệ thống) — máy này chưa có sẵn terraform/gh CLI.

---

## 📁 Cấu trúc backend

```
backend/
├── requirements.txt
├── .env.example
└── app/
    ├── main.py                      # App factory + exception handlers (domain → HTTP)
    ├── core/                        # Hạ tầng dùng chung
    │   ├── config.py                #   Settings (pydantic-settings, đọc .env)
    │   ├── database.py              #   Async engine + session factory + Base
    │   └── dependencies.py          #   get_current_user_id (stub), get_job_tracker, get_storage
    ├── shared/                      # Tiện ích cross-module
    │   ├── enums.py                 #   Python enums ↔ PG ENUM types
    │   ├── exceptions.py            #   Domain exceptions (service không import HTTPException)
    │   ├── messaging.py             #   MessagePublisher (Protocol) + SQSPublisher + InMemoryPublisher
    │   ├── job_tracker.py           #   Trạng thái background job trong Redis
    │   └── storage.py               #   FileStorage (Protocol) + S3Storage
    ├── modules/                     # Mỗi module: router / schemas / service / models
    │   ├── auth/                    #   ★ JWT authentication
    │   │   ├── models.py            #     User
    │   │   ├── security.py          #     bcrypt + PyJWT (hàm thuần, chống timing attack)
    │   │   ├── service.py           #     AuthService — register / authenticate
    │   │   ├── schemas.py           #     RegisterRequest, UserResponse, TokenResponse
    │   │   ├── dependencies.py      #     get_current_user (nạp User, chặn tài khoản khóa)
    │   │   └── router.py            #     POST /auth/register, /auth/login, GET /auth/me
    │   ├── properties/              #   ★ CRUD tòa nhà / phòng / dịch vụ / chỉ số công tơ
    │   │   ├── models.py            #     Property, Room, UtilityService, MeterReading
    │   │   ├── schemas.py           #     Create/Update (PATCH exclude_unset) /Response
    │   │   ├── service.py           #     PropertyService + get_owned_property/room (helper chung)
    │   │   └── router.py            #     /properties, /rooms, /services, /meter-readings
    │   ├── contracts/               #   ★ Hợp đồng — state machine pending→active→terminated
    │   │   ├── models.py            #     Contract, ContractMember
    │   │   ├── schemas.py           #     ContractCreate (validate 1 primary), Update, Response
    │   │   ├── service.py           #     ContractService — activate/terminate/members
    │   │   └── router.py            #     /contracts + /activate /terminate /members
    │   ├── billing/                 #   ★ Module hoàn chỉnh nhất
    │   │   ├── models.py            #     Invoice, InvoiceItem
    │   │   ├── schemas.py           #     Request/Response + BillingTaskMessage (contract SQS)
    │   │   ├── service.py           #     BillingCommandService (API) + InvoiceGenerationService (worker)
    │   │   ├── pdf.py               #     render_invoice_pdf (reportlab)
    │   │   └── router.py            #     POST /billing/close-month (202), GET /billing/jobs/{id}
    │   ├── ocr/                     #   ★ Smart OCR đọc chỉ số đồng hồ
    │   │   ├── engine.py            #     MeterOCREngine — lazy singleton EasyOCR + preprocessing OpenCV
    │   │   ├── service.py           #     MeterOCRService — to_thread + semaphore, chọn candidate tốt nhất
    │   │   ├── schemas.py           #     MeterOCRResponse (value, confidence, needs_confirmation)
    │   │   ├── dependencies.py      #     Singleton providers (engine, semaphore)
    │   │   └── router.py            #     POST /ocr/meter-reading, GET /ocr/health
    │   ├── matching/                #   ★ Engine ghép phòng (chưa có router/DB)
    │   │   ├── engine.py            #     RoommateMatchingEngine — filter-then-rank, weighted cosine
    │   │   ├── schemas.py           #     HabitProfile (9 features + deal-breakers), MatchResult
    │   │   └── mock_data.py         #     Demo 8 persona: python -m app.modules.matching.mock_data
    │   └── expenses/                #   ★ Chia tiền chi tiêu (Splitwise model)
    │       ├── models.py            #     ExpenseGroup/Member, Expense, ExpenseShare, Settlement
    │       ├── schemas.py           #     ExpenseCreate (validate theo split_method), Balance...
    │       ├── service.py           #     ExpenseService — chia tiền, số dư, greedy suggest
    │       └── router.py            #     /expense-groups + expenses/balances/settlements
    └── workers/
        └── billing_worker.py        # SQS consumer — process độc lập, scale riêng
```

## 📁 Cấu trúc frontend

```
frontend/                            # Next.js 16 + React 19 + Tailwind v4
├── .env.local                       # NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
└── src/
    ├── lib/
    │   ├── api.ts                   # Fetch wrapper (JWT, 401→/login) + mọi endpoint + fmtMoney
    │   └── types.ts                 # Types khớp Pydantic (tiền Decimal = string!)
    ├── components/ui.tsx            # Button/Input/Select/Card/Badge/Table
    └── app/
        ├── login/ + register/       # Auth
        └── (app)/                   # Layout có nav + auth guard
            ├── dashboard/           # Danh sách + tạo nhà trọ
            ├── properties/[id]/     # 4 tab: Phòng/Dịch vụ/Hợp đồng/Hóa đơn (chốt tháng + poll job)
            └── expenses/ + [id]/    # Nhóm chia tiền: số dư, gợi ý trả nợ, settlements
```

## 🚀 Chạy local (đã kiểm chứng end-to-end 2026-07-07)

```bash
# 1. Hạ tầng (postgres:5434, redis:6380, localstack:4566 — tự tạo queue/DLQ/bucket)
docker compose up -d

# 2. Backend
cd backend
pip install -r requirements.txt
copy .env.example .env

# 3. Schema + dữ liệu demo (in ra X-User-Id và property_id để test)
python -m alembic upgrade head
python -m scripts.seed_demo

# 4. Chạy (2 terminal riêng) — trên Windows thêm PYTHONUTF8=1
uvicorn app.main:app --reload                      # Terminal 1 — API (docs: /docs)
python -m app.workers.billing_worker               # Terminal 2 — Worker

# 5. Frontend (Terminal 3) — chạy ở localhost:3001 trên máy này (3000 bị Grafana cũ chiếm)
cd ../frontend && npm install && npm run dev
```

Test luồng chốt tháng (auth bằng JWT):
```bash
# Login lấy token (hoặc dùng nút Authorize trong /docs)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=chunha@smartroom.demo&password=smartroom123" | jq -r .access_token)

curl -X POST http://localhost:8000/api/v1/billing/close-month \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"property_id":"<property_id từ seed>","period":"2026-07-01"}'
# -> 202 + job_id -> poll GET /api/v1/billing/jobs/{job_id}
# Kiểm tra PDF: docker exec smartroom-localstack awslocal s3 ls s3://smartroom-invoices --recursive
```

⚠️ Máy dev này còn container của dự án cũ (finding-rooms: `smartroom-db`, `smartroom-redis`, `backend-db-1`...) chiếm port 5432/5433/6379 — compose của SmartRoom cố tình dùng 5434/6380. Nếu dọn các container cũ thì có thể đổi về port chuẩn.

## 📋 Việc tiếp theo (backlog)

- [x] ~~docker-compose.yml~~ + ~~Alembic~~ — xong 2026-07-07, e2e đã kiểm chứng
- [x] ~~Module auth JWT~~ — xong 2026-07-07 (login demo: `chunha@smartroom.demo` / `smartroom123`)
- [x] ~~Refresh token + rate-limit login~~ — xong 2026-07-07
- [x] ~~Revocation list logout + refresh dùng-một-lần~~ — xong 2026-07-08
- [x] ~~Đổi mật khẩu + role landlord tự cấp~~ — xong 2026-07-08
- [ ] **Auth còn lại**: quên mật khẩu (cần email production)
- [x] ~~Module properties/contracts CRUD~~ — xong 2026-07-07, e2e toàn trình đã kiểm chứng
- [x] ~~Module expenses~~ — xong 2026-07-07, e2e đã kiểm chứng (backend MVP hoàn chỉnh 🎉)
- [x] ~~Frontend Next.js MVP~~ — xong 2026-07-07 (login/dashboard/property 4 tab/expenses)
- [ ] **Frontend nâng cao**: trang tenant (xem hóa đơn của mình), presigned URL tải PDF, sửa/xóa phòng-dịch vụ trên UI, chia ratio/exact trên UI, loading states, react-query
- [ ] **Expenses nâng cao**: rời nhóm (chặn khi balance ≠ 0), sửa khoản chi, gắn nhóm với room/contract, OCR hóa đơn từ `receipt_image_url`
- [ ] **PDF tiếng Việt**: đăng ký font TTF (Roboto/Noto Sans) trong `billing/pdf.py` — Helvetica không render được dấu
- [x] ~~Presigned URL S3~~ — xong 2026-07-07 (landlord; tenant chờ trang tenant)
- [x] ~~Terraform SQS/DLQ/S3/SES~~ — xong 2026-07-08, verify bằng LocalStack
- [x] ~~Unit tests logic thuần~~ — 30 tests (chia tiền, matching, OCR, security)
- [x] ~~Integration tests~~ — xong 2026-07-08 (Postgres thật, cả local lẫn CI)
- [x] ~~CI GitHub Actions~~ — file đã có, verify run khi push GitHub lần đầu
- [x] ~~Notification email khi hóa đơn phát hành~~ — xong 2026-07-08 (SES; Zalo backlog)
- [x] ~~OCR: ảnh S3 + confirm vào meter_readings~~ — xong 2026-07-07, test OCR thật chính xác 100%
- [ ] **OCR nâng cao**: crop ROI mặt số (detect vùng hiển thị trước khi OCR — cần khi ảnh thật nhiều nhiễu), test với ảnh đồng hồ thật, bake model weights vào Docker image (`OCR_MODEL_DIR`)
- [ ] **Matching hoàn thiện**: bảng `user_habit_profiles` (migration mới), router `POST /matching/suggestions`, lấy candidates từ DB theo khu vực/tin đăng, cache kết quả vào Redis, học trọng số từ feedback match thành công

## ⚠️ Ràng buộc nghiệp vụ xử lý ở service layer (DB không ép được)

1. `SUM(expense_shares.share_amount)` phải bằng `expenses.amount`.
2. `invoices.status` cập nhật theo `paid_amount` khi ghi nhận `payments`.
3. Kỳ (`period`) luôn chuẩn hóa về ngày 01 của tháng (validator trong `CloseMonthRequest`).
