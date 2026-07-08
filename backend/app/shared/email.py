"""Email abstraction — SES production/LocalStack, FakeEmailSender khi test."""

import asyncio
from typing import Protocol

from app.shared.aws import boto3_client


class EmailSender(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


class SESEmailSender:
    def __init__(self, sender: str) -> None:
        self._sender = sender
        self._client = boto3_client("ses")

    async def send(self, to: str, subject: str, body: str) -> None:
        await asyncio.to_thread(
            self._client.send_email,
            Source=self._sender,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
