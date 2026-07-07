"""Pydantic schemas cho module OCR."""

from pydantic import BaseModel, Field


class OCRCandidateSchema(BaseModel):
    text: str
    confidence: float = Field(ge=0, le=1)


class MeterOCRResponse(BaseModel):
    """Kết quả đọc chỉ số — LUÔN cần người dùng xác nhận trước khi lưu meter_readings."""

    value: int = Field(description="Chỉ số đọc được (candidate tốt nhất)")
    raw_text: str = Field(description="Chuỗi gốc OCR trả về, giữ cả số 0 đầu")
    confidence: float = Field(ge=0, le=1)
    needs_confirmation: bool = Field(
        description="True nếu confidence thấp — frontend phải highlight cho user kiểm tra"
    )
    candidates: list[OCRCandidateSchema] = Field(
        description="Các cụm số khác phát hiện được, để user chọn lại nếu value sai"
    )


class OCRHealthResponse(BaseModel):
    model_ready: bool
    detail: str
