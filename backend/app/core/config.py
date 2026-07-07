"""Cấu hình tập trung — đọc từ biến môi trường / file .env (12-factor)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "local"
    api_v1_prefix: str = "/api/v1"

    # --- Auth ---
    # Production: BẮT BUỘC override qua env (secrets manager), không dùng default này
    jwt_secret_key: str = "dev-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    database_url: str = (
        "postgresql+asyncpg://smartroom:smartroom@localhost:5432/smartroom"
    )
    redis_url: str = "redis://localhost:6379/0"

    aws_region: str = "ap-southeast-1"
    # Trỏ về LocalStack/ElasticMQ khi dev local; None = AWS thật
    aws_endpoint_url: str | None = None
    # Dev local: test/test cho LocalStack. Production: để trống -> IAM role
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    sqs_billing_queue_url: str = ""
    s3_invoice_bucket: str = "smartroom-invoices"

    # --- OCR ---
    ocr_gpu: bool = False
    # Bake sẵn model weights vào Docker image rồi trỏ đường dẫn ở đây
    # để tránh download ~64MB lúc runtime; None = thư mục mặc định ~/.EasyOCR
    ocr_model_dir: str | None = None
    ocr_max_concurrency: int = 2   # số inference đồng thời tối đa
    ocr_max_image_mb: int = 8


@lru_cache
def get_settings() -> Settings:
    return Settings()
