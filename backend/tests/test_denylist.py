"""Unit tests cho TokenDenylist + claim jti trong token."""

import asyncio

from app.modules.auth.denylist import TokenDenylist
from app.modules.auth.security import create_refresh_token, decode_refresh_token
from uuid import uuid4


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value
        if ex is not None:
            self.ttls[key] = ex

    async def exists(self, key: str) -> int:
        return 1 if key in self.store else 0


def test_revoke_va_kiem_tra() -> None:
    denylist = TokenDenylist(FakeRedis())  # type: ignore[arg-type]

    async def run() -> None:
        assert await denylist.is_revoked("abc") is False
        await denylist.revoke("abc", ttl_seconds=100)
        assert await denylist.is_revoked("abc") is True
        assert await denylist.is_revoked("khac") is False

    asyncio.run(run())


def test_ttl_toi_thieu_1_giay() -> None:
    """Token sắp hết hạn (ttl<=0) vẫn phải vào denylist."""
    fake = FakeRedis()
    denylist = TokenDenylist(fake)  # type: ignore[arg-type]
    asyncio.run(denylist.revoke("x", ttl_seconds=-5))
    assert fake.ttls["denylist:jti:x"] == 1


def test_moi_token_co_jti_rieng() -> None:
    user_id = uuid4()
    jti1 = decode_refresh_token(create_refresh_token(user_id))["jti"]
    jti2 = decode_refresh_token(create_refresh_token(user_id))["jti"]
    assert jti1 and jti2 and jti1 != jti2
