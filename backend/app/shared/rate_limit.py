"""Rate limiter fixed-window trên Redis.

Fixed window đủ tốt cho chống brute-force login (sai số biên cửa sổ
không quan trọng với use-case này); cần chính xác hơn thì nâng cấp
sliding window log sau.
"""

from redis.asyncio import Redis

from app.shared.exceptions import RateLimitExceededError


class FixedWindowRateLimiter:
    def __init__(
        self, redis: Redis, prefix: str, max_attempts: int, window_seconds: int
    ) -> None:
        self._redis = redis
        self._prefix = prefix
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds

    async def hit(self, key: str) -> None:
        """Ghi nhận 1 lần thử. Vượt ngưỡng trong cửa sổ -> RateLimitExceededError."""
        redis_key = f"ratelimit:{self._prefix}:{key}"
        count = await self._redis.incr(redis_key)
        if count == 1:
            # Key mới -> đặt TTL mở cửa sổ; các lần sau giữ nguyên TTL cũ
            await self._redis.expire(redis_key, self._window_seconds)
        if count > self._max_attempts:
            raise RateLimitExceededError(
                f"Thử quá {self._max_attempts} lần — đợi "
                f"{self._window_seconds}s rồi thử lại"
            )
