"""Các FastAPI dependencies dùng chung giữa các module."""

from functools import lru_cache
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis

from app.core.config import get_settings
from app.modules.auth.security import decode_access_token
from app.shared.job_tracker import JobTracker
from app.shared.storage import S3Storage

# tokenUrl trỏ về endpoint login -> Swagger UI có nút Authorize
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user_id(
    token: Annotated[str, Depends(_oauth2_scheme)],
) -> UUID:
    """Xác thực JWT Bearer token, trả về user id trong claim `sub`.

    Không query DB — đủ cho các endpoint tự kiểm tra quyền sở hữu trên dữ liệu.
    Endpoint cần cả profile/kiểm tra khóa tài khoản: dùng
    modules.auth.dependencies.get_current_user.
    """
    try:
        payload = decode_access_token(token)
        return UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


@lru_cache
def _redis_client() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


def get_job_tracker() -> JobTracker:
    return JobTracker(_redis_client())


@lru_cache
def get_storage() -> S3Storage:
    return S3Storage(bucket=get_settings().s3_invoice_bucket)
