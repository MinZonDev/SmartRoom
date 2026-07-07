"""Dependencies riêng của module auth."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user_id
from app.modules.auth.models import User


async def get_current_user(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """Nạp User từ DB — dùng khi endpoint cần cả profile, không chỉ id.

    Cũng chặn token còn hạn của user đã bị khóa (is_active=False).
    """
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản không tồn tại hoặc đã bị khóa",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
