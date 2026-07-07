"""HTTP layer module auth."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.core.dependencies import get_redis_client
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.modules.auth.service import AuthService
from app.shared.exceptions import NotFoundError
from app.shared.rate_limit import FixedWindowRateLimiter


def get_login_rate_limiter() -> FixedWindowRateLimiter:
    settings = get_settings()
    return FixedWindowRateLimiter(
        redis=get_redis_client(),
        prefix="login",
        max_attempts=settings.login_rate_limit_attempts,
        window_seconds=settings.login_rate_limit_window_seconds,
    )

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    summary="Đăng ký tài khoản",
)
async def register(
    payload: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    return await AuthService(session).register(payload)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Đăng nhập (OAuth2 password flow — username = email)",
)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[AsyncSession, Depends(get_session)],
    limiter: Annotated[FixedWindowRateLimiter, Depends(get_login_rate_limiter)],
) -> TokenResponse:
    # Đếm mọi lần thử theo email (kể cả thành công) — chống brute-force
    await limiter.hit(form.username.lower())
    return await AuthService(session).authenticate(form.username, form.password)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Đổi refresh token lấy cặp access + refresh mới",
)
async def refresh_tokens(
    payload: RefreshRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    return await AuthService(session).refresh(payload.refresh_token)


@router.get("/me", response_model=UserResponse, summary="Thông tin user hiện tại")
async def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@router.get(
    "/users/lookup",
    response_model=UserResponse,
    summary="Tìm user theo email (để thêm vào hợp đồng / nhóm chia tiền)",
)
async def lookup_user(
    email: str,
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active:
        raise NotFoundError(f"Không tìm thấy user với email {email}")
    return user
