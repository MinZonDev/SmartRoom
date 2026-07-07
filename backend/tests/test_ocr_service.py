"""Unit tests cho MeterOCRService — dùng engine giả, không cần torch/EasyOCR."""

import asyncio

import pytest

from app.modules.ocr.engine import OCRCandidate
from app.modules.ocr.service import MeterOCRService
from app.shared.exceptions import NoReadingDetectedError


class FakeEngine:
    """Engine giả trả về candidates định sẵn — cùng interface read_digits."""

    def __init__(self, candidates: list[OCRCandidate]) -> None:
        self._candidates = candidates

    def read_digits(self, image_bytes: bytes) -> list[OCRCandidate]:
        return self._candidates


def _service(candidates: list[OCRCandidate]) -> MeterOCRService:
    return MeterOCRService(
        engine=FakeEngine(candidates),  # type: ignore[arg-type]
        semaphore=asyncio.Semaphore(1),
    )


def test_chon_candidate_tot_nhat() -> None:
    service = _service(
        [
            OCRCandidate(text="12345", confidence=0.9),
            OCRCandidate(text="678", confidence=0.5),
        ]
    )
    result = asyncio.run(service.read_meter_image(b"fake"))
    assert result.value == 12345
    assert result.needs_confirmation is False


def test_loai_serial_number_qua_dai() -> None:
    """Chuỗi >9 chữ số (serial trên mặt đồng hồ) không thể là chỉ số."""
    service = _service(
        [
            OCRCandidate(text="1234567890123", confidence=0.99),  # serial
            OCRCandidate(text="4567", confidence=0.7),
        ]
    )
    result = asyncio.run(service.read_meter_image(b"fake"))
    assert result.value == 4567


def test_confidence_thap_yeu_cau_xac_nhan() -> None:
    service = _service([OCRCandidate(text="8888", confidence=0.3)])
    result = asyncio.run(service.read_meter_image(b"fake"))
    assert result.needs_confirmation is True


def test_khong_co_so_nao_raise() -> None:
    service = _service([OCRCandidate(text="ab", confidence=0.9)])
    with pytest.raises(NoReadingDetectedError):
        asyncio.run(service.read_meter_image(b"fake"))


def test_giu_so_0_dau_trong_raw_text() -> None:
    """Chỉ số '00123' -> value 123 nhưng raw_text giữ nguyên để hiển thị."""
    service = _service([OCRCandidate(text="00123", confidence=0.8)])
    result = asyncio.run(service.read_meter_image(b"fake"))
    assert result.value == 123
    assert result.raw_text == "00123"
