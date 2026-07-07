"""Business logic module auth — không import gì từ FastAPI."""

import asyncio
from uuid import UUID

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.auth.models import User
from app.modules.auth.schemas import RegisterRequest, TokenResponse
from app.modules.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.shared.exceptions import EmailAlreadyExistsError, InvalidCredentialsError


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def register(self, payload: RegisterRequest) -> User:
        existing_id = await self._session.scalar(
            select(User.id).where(User.email == payload.email)
        )
        if existing_id is not None:
            raise EmailAlreadyExistsError(f"Email {payload.email} đã được đăng ký")

        # bcrypt CPU-bound -> thread để không block event loop
        password_hash = await asyncio.to_thread(hash_password, payload.password)
        user = User(
            full_name=payload.full_name,
            email=payload.email,
            phone=payload.phone,
            password_hash=password_hash,
        )
        self._session.add(user)
        await self._session.commit()
        return user

    async def authenticate(self, email: str, password: str) -> TokenResponse:
        user = await self._session.scalar(select(User).where(User.email == email))

        # LUÔN chạy verify kể cả khi user không tồn tại (dummy hash bên trong)
        # -> thời gian phản hồi không tiết lộ email nào có trong hệ thống
        password_ok = await asyncio.to_thread(
            verify_password, password, user.password_hash if user else None
        )
        if user is None or not password_ok or not user.is_active:
            raise InvalidCredentialsError("Email hoặc mật khẩu không đúng")

        return self._issue_tokens(user.id)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        """Đổi refresh token lấy cặp token mới (rotation).

        Stateless — chưa có danh sách thu hồi server-side; token cũ vẫn
        dùng được tới khi hết hạn (revocation list Redis: backlog).
        """
        try:
            payload = decode_refresh_token(refresh_token)
            user_id = UUID(payload["sub"])
        except (jwt.InvalidTokenError, KeyError, ValueError):
            raise InvalidCredentialsError(
                "Refresh token không hợp lệ hoặc đã hết hạn"
            ) from None

        user = await self._session.get(User, user_id)
        if user is None or not user.is_active:
            raise InvalidCredentialsError("Tài khoản không tồn tại hoặc đã bị khóa")
        return self._issue_tokens(user.id)

    @staticmethod
    def _issue_tokens(user_id: UUID) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(user_id),
            refresh_token=create_refresh_token(user_id),
            expires_in=get_settings().jwt_access_token_expire_minutes * 60,
        )
