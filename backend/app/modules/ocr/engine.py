"""EasyOCR engine đọc chỉ số đồng hồ điện/nước.

Thiết kế:
- Lazy singleton: model chỉ nạp khi cần, threading.Lock chống nạp trùng
  khi nhiều request đến cùng lúc.
- `import easyocr` đặt bên trong load() — torch (~500MB RAM) không bị kéo vào
  các process không dùng OCR (vd: billing worker).
- load() và read_digits() đều BLOCKING — caller phải chạy qua asyncio.to_thread.
- Class không phụ thuộc FastAPI: tái sử dụng được trong SQS worker khi cần scale.
"""

import threading
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from app.shared.exceptions import InvalidImageError


@dataclass(frozen=True)
class OCRCandidate:
    """Một chuỗi số EasyOCR phát hiện được trên ảnh."""

    text: str
    confidence: float


class MeterOCREngine:
    _ALLOWLIST = "0123456789"  # đồng hồ chỉ có chữ số
    _MAX_SIDE_PX = 1280        # resize ảnh lớn để giảm thời gian inference

    def __init__(self, gpu: bool = False, model_dir: str | None = None) -> None:
        self._gpu = gpu
        self._model_dir = model_dir
        self._reader: Any | None = None  # easyocr.Reader — import trễ
        self._init_lock = threading.Lock()

    @property
    def is_ready(self) -> bool:
        return self._reader is not None

    def load(self) -> None:
        """Nạp model vào memory (blocking, 5-15s lần đầu). Idempotent, thread-safe.

        Double-checked locking: request OCR đến trước khi warm-up xong sẽ
        chờ trên lock thay vì nạp thêm một model nữa.
        """
        if self._reader is not None:
            return
        with self._init_lock:
            if self._reader is not None:
                return
            import easyocr  # noqa: PLC0415 — import trễ có chủ đích (xem docstring module)

            self._reader = easyocr.Reader(
                ["en"],
                gpu=self._gpu,
                model_storage_directory=self._model_dir,
                verbose=False,
            )

    def read_digits(self, image_bytes: bytes) -> list[OCRCandidate]:
        """Đọc mọi cụm chữ số trên ảnh (blocking — gọi qua asyncio.to_thread)."""
        self.load()
        assert self._reader is not None
        image = self._preprocess(image_bytes)
        raw = self._reader.readtext(image, allowlist=self._ALLOWLIST, detail=1)
        return [
            OCRCandidate(text=text, confidence=float(conf))
            for _bbox, text, conf in raw
            if text.strip()
        ]

    @classmethod
    def _preprocess(cls, image_bytes: bytes) -> np.ndarray:
        """Chuẩn hóa ảnh: decode → resize → grayscale → tăng tương phản CLAHE.

        Đồng hồ thường chụp trong hộp kỹ thuật thiếu sáng nên CLAHE cải thiện
        đáng kể tỷ lệ đọc đúng.
        """
        buffer = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if image is None:
            raise InvalidImageError("File không phải ảnh hợp lệ hoặc đã hỏng")

        height, width = image.shape[:2]
        longest = max(height, width)
        if longest > cls._MAX_SIDE_PX:
            scale = cls._MAX_SIDE_PX / longest
            image = cv2.resize(
                image,
                (int(width * scale), int(height * scale)),
                interpolation=cv2.INTER_AREA,
            )

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(gray)
