"""Factory tạo boto3 client theo Settings.

Truyền credentials tường minh (thay vì dựa vào OS env) vì .env chỉ được
pydantic-settings đọc. Production trên EC2/ECS: để trống access key
trong env — boto3 tự dùng IAM instance role.
"""

from typing import Any

import boto3

from app.core.config import get_settings


def boto3_client(service: str) -> Any:
    settings = get_settings()
    kwargs: dict[str, Any] = {
        "region_name": settings.aws_region,
        "endpoint_url": settings.aws_endpoint_url,
    }
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client(service, **kwargs)
