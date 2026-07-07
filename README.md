# SmartRoom

Nền tảng quản lý không gian sống, nhà trọ và ghép phòng tích hợp AI.

**Tính năng MVP** (đã chạy end-to-end):
- 🏠 Quản lý nhà trọ: tòa nhà / phòng / dịch vụ / hợp đồng (state machine) / chỉ số công tơ
- 🧾 Chốt tháng event-driven: API 202 → SQS → worker tính tiền + sinh PDF → S3
- 💸 Chia tiền nhóm kiểu Splitwise: 3 kiểu chia, số dư dẫn xuất, gợi ý trả nợ tối ưu
- 🤖 AI: OCR chỉ số đồng hồ (EasyOCR), gợi ý ghép phòng (weighted cosine, scikit-learn)
- 🔐 Auth JWT (PyJWT + bcrypt)

**Stack**: FastAPI + SQLAlchemy 2 async · PostgreSQL · Redis · AWS SQS/S3 (LocalStack khi dev) · Next.js 16 + Tailwind v4

## Bắt đầu

👉 **Đọc [`project.md`](./project.md)** — nguồn sự thật về tiến độ, quyết định kỹ thuật, hướng dẫn chạy local chi tiết và backlog.

```bash
docker compose up -d                      # postgres:5434, redis:6380, localstack:4566
cd backend && pip install -r requirements.txt && copy .env.example .env
python -m alembic upgrade head && python -m scripts.seed_demo
uvicorn app.main:app --reload             # + python -m app.workers.billing_worker (terminal khác)
cd ../frontend && npm install && npm run dev
```

Tài khoản demo: `chunha@smartroom.demo` / `smartroom123`

## Tài liệu

- `project.md` — nhật ký & tiến độ (đọc đầu tiên)
- `docs/database/` — ERD (draw.io) + schema SQL gốc
- API docs: `http://localhost:8000/docs`
