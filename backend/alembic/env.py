"""Alembic environment — async engine, URL đọc từ app Settings."""

import asyncio
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.core.database import Base

# Import mọi models để Base.metadata đầy đủ (bắt buộc cho autogenerate)
from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.billing import models as _billing_models  # noqa: F401
from app.modules.contracts import models as _contracts_models  # noqa: F401
from app.modules.properties import models as _properties_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def include_object(
    obj: Any, name: str, type_: str, reflected: bool, compare_to: Any
) -> bool:
    """Bỏ qua các bảng có trong DB nhưng chưa có ORM model.

    Schema đầy đủ 16 bảng (gồm cả expenses) được tạo bởi initial migration,
    nhưng ORM mới map một phần — không để autogenerate đề xuất DROP các bảng đó.
    """
    if type_ == "table" and reflected and compare_to is None:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with engine.connect() as connection:
        await connection.run_sync(_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
