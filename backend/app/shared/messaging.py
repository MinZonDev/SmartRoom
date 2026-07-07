"""Message queue abstraction.

Dùng Protocol để service layer chỉ phụ thuộc interface (DIP) —
production dùng SQS, unit test có thể inject InMemoryPublisher.
boto3 là sync client nên mọi lời gọi được đẩy sang thread để không block event loop.
"""

import asyncio
import json
from functools import lru_cache
from typing import Any, Protocol

from app.core.config import get_settings
from app.shared.aws import boto3_client


class MessagePublisher(Protocol):
    async def publish(self, payload: dict[str, Any]) -> None: ...


class SQSPublisher:
    def __init__(self, queue_url: str) -> None:
        self._queue_url = queue_url
        self._client = boto3_client("sqs")

    async def publish(self, payload: dict[str, Any]) -> None:
        await asyncio.to_thread(
            self._client.send_message,
            QueueUrl=self._queue_url,
            MessageBody=json.dumps(payload, default=str),
        )


class InMemoryPublisher:
    """Dùng cho unit test — gom message vào list thay vì gửi đi."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def publish(self, payload: dict[str, Any]) -> None:
        self.messages.append(payload)


@lru_cache
def get_billing_publisher() -> SQSPublisher:
    return SQSPublisher(queue_url=get_settings().sqs_billing_queue_url)
