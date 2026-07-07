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

    async def presigned_url(self, key: str, expires_seconds: int = 900) -> str:
        """URL tải file có chữ ký, tự hết hạn — không bao giờ public bucket."""
        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_seconds,
        )

    def key_from_uri(self, uri: str) -> str:
        """'s3://bucket/path/file.pdf' -> 'path/file.pdf'."""
        return uri.removeprefix(f"s3://{self._bucket}/")
