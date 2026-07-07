"""Tiện ích mật khẩu + JWT — hàm thuần, không đụng DB/HTTP.

bcrypt là CPU-bound có chủ đích (~200ms) — caller phải gọi hash/verify
qua asyncio.to_thread để không block event loop.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import bcrypt
import jwt

from app.core.config import get_settings

# bcrypt chỉ dùng 72 byte đầu của mật khẩu — validate ở schema
BCRYPT_MAX_PASSWORD_BYTES = 72

# Hash của chuỗi ngẫu nhiên, dùng verify "giả" khi email không tồn tại
# để thời gian phản hồi không tiết lộ email nào có trong hệ thống (timing attack)
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password-for-timing", bcrypt.gensalt())


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, password_hash: str | None) -> bool:
    """So khớp mật khẩu. password_hash=None -> verify với dummy hash (chống timing attack)."""
    target = password_hash.encode("utf-8") if password_hash else _DUMMY_HASH
    result = bcrypt.checkpw(plain.encode("utf-8"), target)
    return result and password_hash is not None


def create_access_token(user_id: UUID) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Giải mã + verify chữ ký & hạn. Raise jwt.InvalidTokenError nếu không hợp lệ."""
    settings = get_settings()
    payload: dict[str, Any] = jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Không phải access token")
    return payload
