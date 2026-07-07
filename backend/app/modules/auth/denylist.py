"""Danh sách thu hồi token (denylist) trên Redis.

Key tự hết hạn đúng bằng thời gian sống còn lại của token — không rác Redis.
Dùng cho: logout (thu hồi refresh token) và rotation (refresh dùng-một-lần).
"""

from redis.asyncio import Redis


class TokenDenylist:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @staticmethod
    def _key(jti: str) -> str:
        return f"denylist:jti:{jti}"

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        # TTL tối thiểu 1s — token sắp hết hạn vẫn phải vào denylist
        await self._redis.set(self._key(jti), "1", ex=max(ttl_seconds, 1))

    async def is_revoked(self, jti: str) -> bool:
        return bool(await self._redis.exists(self._key(jti)))
