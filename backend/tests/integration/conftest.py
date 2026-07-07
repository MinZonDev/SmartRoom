"""Fixtures cho integration tests — cần Postgres thật.

- Local : docker compose up -d (postgres map host port 5434) là chạy được.
- CI    : job backend-tests có postgres service, set TEST_DATABASE_URL.
- Không có Postgres -> tests tự skip (không fail).

Mỗi test nhận schema SẠCH (drop_all + create_all) — chậm hơn truncate một
chút nhưng đơn giản và an toàn event-loop (mọi fixture đều function-scoped).
"""

import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.database import Base

# Import mọi models để Base.metadata đầy đủ trước khi create_all
from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.billing import models as _billing_models  # noqa: F401
from app.modules.contracts import models as _contracts_models  # noqa: F401
from app.modules.expenses import models as _expenses_models  # noqa: F401
from app.modules.properties import models as _properties_models  # noqa: F401

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://smartroom:smartroom@localhost:5434/smartroom_test",
)
_TEST_DB_NAME = TEST_DATABASE_URL.rsplit("/", 1)[1]

_db_ready = False


async def _ensure_test_database() -> None:
    """Tạo database test nếu chưa có; Postgres không chạy -> skip."""
    global _db_ready
    if _db_ready:
        return
    admin_url = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
    try:
        admin_engine = create_async_engine(
            admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool
        )
        async with admin_engine.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": _TEST_DB_NAME},
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{_TEST_DB_NAME}"'))
        await admin_engine.dispose()
        _db_ready = True
    except Exception as exc:  # noqa: BLE001 — mọi lỗi kết nối đều skip
        pytest.skip(f"Postgres test không khả dụng ({exc.__class__.__name__})")


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    await _ensure_test_database()
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


class FakeStorage:
    """FileStorage giả — không đụng S3, ghi nhận key đã upload."""

    def __init__(self) -> None:
        self.uploaded: list[str] = []

    async def upload(self, key: str, content: bytes, content_type: str) -> str:
        self.uploaded.append(key)
        return f"s3://fake-bucket/{key}"
