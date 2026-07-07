"""Business logic OCR: điều phối inference + chọn kết quả tốt nhất.

Service không đụng tới EasyOCR trực tiếp — chỉ nói chuyện với MeterOCREngine,
nên có thể unit test bằng engine giả không cần torch.
"""

import asyncio

from app.modules.ocr.engine import MeterOCREngine, OCRCandidate
from app.modules.ocr.schemas import MeterOCRResponse, OCRCandidateSchema
from app.shared.exceptions import NoReadingDetectedError

# Chỉ số đồng hồ điện/nước dân dụng thường có 4-8 chữ số
_MIN_DIGITS = 3
_MAX_DIGITS = 9
# Dưới ngưỡng này frontend phải bắt user kiểm tra kỹ trước khi xác nhận
_CONFIDENCE_THRESHOLD = 0.55


class MeterOCRService:
    def __init__(self, engine: MeterOCREngine, semaphore: asyncio.Semaphore) -> None:
        self._engine = engine
        self._semaphore = semaphore

    async def read_meter_image(self, image_bytes: bytes) -> MeterOCRResponse:
        """Đọc chỉ số từ ảnh đồng hồ.

        Inference là CPU-bound sync → chạy trong thread; semaphore giới hạn
        số inference đồng thời để không nghẽn CPU/RAM của API process.
        """
        async with self._semaphore:
            candidates = await asyncio.to_thread(
                self._engine.read_digits, image_bytes
            )

        plausible = self._filter_plausible(candidates)
        if not plausible:
            raise NoReadingDetectedError(
                "Không tìm thấy chỉ số trên ảnh — hãy chụp gần và rõ mặt số hơn"
            )

        best = max(plausible, key=self._score)
        return MeterOCRResponse(
            value=int(best.text),
            raw_text=best.text,
            confidence=round(best.confidence, 4),
            needs_confirmation=best.confidence < _CONFIDENCE_THRESHOLD,
            candidates=[
                OCRCandidateSchema(text=c.text, confidence=round(c.confidence, 4))
                for c in plausible
            ],
        )

    @staticmethod
    def _filter_plausible(candidates: list[OCRCandidate]) -> list[OCRCandidate]:
        """Loại các cụm số không thể là chỉ số đồng hồ (quá ngắn/quá dài)."""
        return [
            c
            for c in candidates
            if c.text.isdigit() and _MIN_DIGITS <= len(c.text) <= _MAX_DIGITS
        ]

    @staticmethod
    def _score(candidate: OCRCandidate) -> float:
        """Ưu tiên confidence, cộng nhẹ theo độ dài — mặt số chính của đồng hồ
        thường là cụm số dài nhất trên ảnh (serial number đã bị chặn bởi _MAX_DIGITS).
        """
        return candidate.confidence + 0.03 * len(candidate.text)
