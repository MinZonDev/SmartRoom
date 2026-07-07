"""HTTP layer module auth."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.auth.schemas import RegisterRequest, TokenResponse, UserResponse
from app.modules.auth.service import AuthService
from app.shared.exceptions import NotFoundError

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
) -> TokenResponse:
    return await AuthService(session).authenticate(form.username, form.password)


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
