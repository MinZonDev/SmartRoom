"""Unit tests cho FixedWindowRateLimiter — dùng FakeRedis, không cần Redis thật."""

import asyncio

import pytest

from app.shared.exceptions import RateLimitExceededError
from app.shared.rate_limit import FixedWindowRateLimiter


class FakeRedis:
    """Chỉ implement incr/expire — đủ cho limiter."""

    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def expire(self, key: str, seconds: int) -> None:
        self.ttls[key] = seconds


def _limiter(fake: FakeRedis, max_attempts: int = 3) -> FixedWindowRateLimiter:
    return FixedWindowRateLimiter(
        redis=fake,  # type: ignore[arg-type]
        prefix="test",
        max_attempts=max_attempts,
        window_seconds=60,
    )


def test_duoi_nguong_khong_chan() -> None:
    limiter = _limiter(FakeRedis())

    async def run() -> None:
        for _ in range(3):
            await limiter.hit("user@x.com")

    asyncio.run(run())  # không raise


def test_vuot_nguong_bi_chan() -> None:
    limiter = _limiter(FakeRedis())

    async def run() -> None:
        for _ in range(3):
            await limiter.hit("user@x.com")
        with pytest.raises(RateLimitExceededError):
            await limiter.hit("user@x.com")

    asyncio.run(run())


def test_key_khac_khong_anh_huong() -> None:
    fake = FakeRedis()
    limiter = _limiter(fake)

    async def run() -> None:
        for _ in range(3):
            await limiter.hit("a@x.com")
        await limiter.hit("b@x.com")  # người khác vẫn login được

    asyncio.run(run())


def test_ttl_chi_dat_khi_key_moi() -> None:
    fake = FakeRedis()
    limiter = _limiter(fake)

    async def run() -> None:
        await limiter.hit("a@x.com")
        await limiter.hit("a@x.com")

    asyncio.run(run())
    assert fake.ttls == {"ratelimit:test:a@x.com": 60}
