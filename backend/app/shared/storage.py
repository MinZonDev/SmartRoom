"""File storage abstraction — S3 cho production, có thể thay bằng local disk khi test."""

import asyncio
from typing import Protocol

from app.shared.aws import boto3_client


class FileStorage(Protocol):
    async def upload(self, key: str, content: bytes, content_type: str) -> str: ...


class S3Storage:
    def __init__(self, bucket: str) -> None:
        self._bucket = bucket
        self._client = boto3_client("s3")

    async def upload(self, key: str, content: bytes, content_type: str) -> str:
        """Upload file và trả về S3 URI. Chạy trong thread vì boto3 là sync."""
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )
        return f"s3://{self._bucket}/{key}"
