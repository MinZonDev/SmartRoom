"""Business logic module auth — không import gì từ FastAPI."""

import asyncio
import time
from typing import Any
from uuid import UUID

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.auth.denylist import TokenDenylist
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
    def __init__(
        self, session: AsyncSession, denylist: TokenDenylist | None = None
    ) -> None:
        self._session = session
        self._denylist = denylist

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
        """Đổi refresh token lấy cặp token mới (rotation, dùng-một-lần).

        Token vừa dùng bị đưa vào denylist ngay — nếu bị đánh cắp và dùng
        lại sẽ nhận 401. Access token vẫn stateless (sống tối đa 60').
        """
        assert self._denylist is not None, "refresh cần denylist"
        try:
            payload = decode_refresh_token(refresh_token)
            user_id = UUID(payload["sub"])
            jti: str = payload["jti"]
        except (jwt.InvalidTokenError, KeyError, ValueError):
            raise InvalidCredentialsError(
                "Refresh token không hợp lệ hoặc đã hết hạn"
            ) from None

        if await self._denylist.is_revoked(jti):
            raise InvalidCredentialsError("Refresh token đã bị thu hồi")

        user = await self._session.get(User, user_id)
        if user is None or not user.is_active:
            raise InvalidCredentialsError("Tài khoản không tồn tại hoặc đã bị khóa")

        await self._denylist.revoke(jti, self._remaining_ttl(payload))
        return self._issue_tokens(user.id)

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> None:
        password_ok = await asyncio.to_thread(
            verify_password, current_password, user.password_hash
        )
        if not password_ok:
            raise InvalidCredentialsError("Mật khẩu hiện tại không đúng")
        user.password_hash = await asyncio.to_thread(hash_password, new_password)
        await self._session.commit()

    async def logout(self, refresh_token: str) -> None:
        """Thu hồi refresh token. Idempotent — token rác/hết hạn cũng trả OK."""
        assert self._denylist is not None, "logout cần denylist"
        try:
            payload = decode_refresh_token(refresh_token)
            jti: str = payload["jti"]
        except (jwt.InvalidTokenError, KeyError):
            return  # token không hợp lệ thì không có gì để thu hồi
        await self._denylist.revoke(jti, self._remaining_ttl(payload))

    @staticmethod
    def _remaining_ttl(payload: dict[str, Any]) -> int:
        return int(payload["exp"] - time.time())

    @staticmethod
    def _issue_tokens(user_id: UUID) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(user_id),
            refresh_token=create_refresh_token(user_id),
            expires_in=get_settings().jwt_access_token_expire_minutes * 60,
        )
