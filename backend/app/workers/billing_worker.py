"""Billing worker — consumer của SQS queue billing.

Chạy như một process độc lập với API (scale riêng trên EC2/ECS):

    python -m app.workers.billing_worker

Cơ chế:
- Long-polling SQS (WaitTimeSeconds=20) để giảm số request rỗng.
- Xử lý thành công -> delete message. Thất bại -> KHÔNG delete, message
  quay lại queue sau visibility timeout để retry; quá maxReceiveCount
  thì SQS tự chuyển vào Dead Letter Queue (cấu hình ở hạ tầng).
- Logic sinh hóa đơn idempotent nên retry không tạo bản ghi trùng.
"""

import asyncio
import logging
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.database import async_session_factory
from app.modules.billing.notifications import InvoiceNotificationService
from app.modules.billing.schemas import BillingTaskMessage
from app.modules.billing.service import InvoiceGenerationService
from app.shared.aws import boto3_client
from app.shared.email import SESEmailSender
from app.shared.job_tracker import JobStatus, JobTracker
from app.shared.storage import FileStorage, S3Storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [billing-worker] %(message)s",
)
logger = logging.getLogger(__name__)


async def process_message(
    body: str, tracker: JobTracker, storage: FileStorage
) -> None:
    """Xử lý 1 message: tính hóa đơn + sinh PDF, cập nhật job status."""
    task = BillingTaskMessage.model_validate_json(body)
    logger.info(
        "Bắt đầu job %s — property=%s period=%s",
        task.job_id, task.property_id, task.period,
    )
    await tracker.set_status(task.job_id, JobStatus.PROCESSING)
    try:
        async with async_session_factory() as session:
            service = InvoiceGenerationService(session, storage)
            summary = await service.generate_for_property(
                task.property_id, task.period
            )
            # Email báo tenant — best-effort: lỗi email không được fail job
            # (hóa đơn đã tạo xong; SQS retry sẽ tạo trùng email chứ không tạo lại hóa đơn)
            if summary.invoice_ids:
                try:
                    notifier = InvoiceNotificationService(
                        session, SESEmailSender(get_settings().ses_sender_email)
                    )
                    sent = await notifier.notify_issued(
                        [UUID(i) for i in summary.invoice_ids]
                    )
                    logger.info("Đã gửi %d email báo hóa đơn", sent)
                except Exception:
                    logger.exception("Gửi email notification thất bại")
    except Exception as exc:
        await tracker.set_status(task.job_id, JobStatus.FAILED, error=str(exc))
        raise
    await tracker.set_status(
        task.job_id, JobStatus.COMPLETED, result=summary.as_dict()
    )
    logger.info(
        "Hoàn thành job %s — tạo %d hóa đơn, bỏ qua %d, lỗi %d",
        task.job_id,
        summary.invoices_created,
        len(summary.skipped),
        len(summary.errors),
    )


async def run_worker(settings: Settings) -> None:
    sqs = boto3_client("sqs")
    tracker = JobTracker(Redis.from_url(settings.redis_url, decode_responses=True))
    storage = S3Storage(bucket=settings.s3_invoice_bucket)
    logger.info("Worker khởi động — queue: %s", settings.sqs_billing_queue_url)

    while True:
        # boto3 sync -> chạy trong thread để không block event loop
        response = await asyncio.to_thread(
            sqs.receive_message,
            QueueUrl=settings.sqs_billing_queue_url,
            MaxNumberOfMessages=5,
            WaitTimeSeconds=20,
        )
        for message in response.get("Messages", []):
            try:
                await process_message(message["Body"], tracker, storage)
            except Exception:
                logger.exception(
                    "Xử lý message thất bại — giữ lại trên queue để retry/DLQ"
                )
                continue
            await asyncio.to_thread(
                sqs.delete_message,
                QueueUrl=settings.sqs_billing_queue_url,
                ReceiptHandle=message["ReceiptHandle"],
            )


if __name__ == "__main__":
    asyncio.run(run_worker(get_settings()))
