"""Pydantic schemas cho module auth."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.auth.security import BCRYPT_MAX_PASSWORD_BYTES


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=20)
    password: str = Field(min_length=8, max_length=BCRYPT_MAX_PASSWORD_BYTES)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # đọc thẳng từ ORM object

    id: UUID
    full_name: str
    email: EmailStr
    phone: str | None
    avatar_url: str | None
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Số giây token còn hiệu lực")
