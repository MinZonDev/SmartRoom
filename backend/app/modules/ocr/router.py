"""HTTP layer module OCR — router mỏng, chỉ validate upload rồi gọi service."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.core.config import get_settings
from app.core.dependencies import get_current_user_id
from app.modules.ocr.dependencies import get_ocr_engine, get_ocr_service
from app.modules.ocr.engine import MeterOCREngine
from app.modules.ocr.schemas import MeterOCRResponse, OCRHealthResponse
from app.modules.ocr.service import MeterOCRService

router = APIRouter(prefix="/ocr", tags=["ocr"])

_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post(
    "/meter-reading",
    response_model=MeterOCRResponse,
    summary="Đọc chỉ số đồng hồ điện/nước từ ảnh",
)
async def read_meter_reading(
    file: UploadFile,
    _current_user_id: Annotated[UUID, Depends(get_current_user_id)],
    service: Annotated[MeterOCRService, Depends(get_ocr_service)],
) -> MeterOCRResponse:
    """Trả về chỉ số + độ tin cậy. Kết quả chỉ mang tính gợi ý —
    client phải cho người dùng XÁC NHẬN trước khi ghi vào meter_readings.
    """
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Chỉ nhận ảnh {', '.join(sorted(_ALLOWED_CONTENT_TYPES))}",
        )

    content = await file.read()
    max_bytes = get_settings().ocr_max_image_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Ảnh vượt quá {get_settings().ocr_max_image_mb}MB",
        )

    return await service.read_meter_image(content)


@router.get(
    "/health",
    response_model=OCRHealthResponse,
    summary="Trạng thái warm-up của model OCR",
)
async def ocr_health(
    engine: Annotated[MeterOCREngine, Depends(get_ocr_engine)],
) -> OCRHealthResponse:
    """Readiness probe riêng cho OCR — server vẫn healthy khi model đang nạp,
    chỉ tính năng OCR là chưa sẵn sàng.
    """
    if engine.is_ready:
        return OCRHealthResponse(model_ready=True, detail="Model đã nạp vào memory")
    return OCRHealthResponse(
        model_ready=False,
        detail="Model đang warm-up — request OCR sẽ tự chờ đến khi nạp xong",
    )
