"""Theo dõi trạng thái background job trong Redis.

Frontend poll GET /billing/jobs/{job_id} để hiển thị tiến độ.
Key tự hết hạn sau 24h — job status là dữ liệu tạm, không cần bền vững.
"""

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from redis.asyncio import Redis


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobTracker:
    _TTL_SECONDS = 60 * 60 * 24

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @staticmethod
    def _key(job_id: str) -> str:
        return f"job:billing:{job_id}"

    async def create(self, job_id: str, meta: dict[str, Any]) -> None:
        data: dict[str, Any] = {
            "job_id": job_id,
            "status": JobStatus.PENDING.value,
            "meta": meta,
            "result": None,
            "error": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._write(job_id, data)

    async def set_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        data = await self.get(job_id) or {"job_id": job_id, "meta": {}}
        data.update(
            status=status.value,
            result=result,
            error=error,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        await self._write(job_id, data)

    async def get(self, job_id: str) -> dict[str, Any] | None:
        raw: str | None = await self._redis.get(self._key(job_id))
        return json.loads(raw) if raw else None

    async def _write(self, job_id: str, data: dict[str, Any]) -> None:
        await self._redis.set(
            self._key(job_id), json.dumps(data, default=str), ex=self._TTL_SECONDS
        )
