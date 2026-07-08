"""ORM models: users, user_roles — khớp schema docs/database/smartroom_mvp_schema.sql."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.enums import UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    avatar_url: Mapped[str | None]
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class UserRoleAssignment(Base):
    """Role phân quyền — một user có thể có nhiều role đồng thời (landlord + tenant)."""

    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), primary_key=True
    )
    role: Mapped[UserRole] = mapped_column(
        SAEnum(
            UserRole, name="user_role", values_callable=lambda e: [m.value for m in e]
        ),
        primary_key=True,
    )
    granted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
