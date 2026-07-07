"""Singleton providers cho module OCR.

Engine và semaphore phải là singleton cấp process — lru_cache đảm bảo
mọi request (và lifespan warm-up) dùng chung một model trong memory.
"""

import asyncio
from functools import lru_cache

from app.core.config import get_settings
from app.modules.ocr.engine import MeterOCREngine
from app.modules.ocr.service import MeterOCRService


@lru_cache
def get_ocr_engine() -> MeterOCREngine:
    settings = get_settings()
    return MeterOCREngine(gpu=settings.ocr_gpu, model_dir=settings.ocr_model_dir)


@lru_cache
def _get_ocr_semaphore() -> asyncio.Semaphore:
    return asyncio.Semaphore(get_settings().ocr_max_concurrency)


def get_ocr_service() -> MeterOCRService:
    return MeterOCRService(engine=get_ocr_engine(), semaphore=_get_ocr_semaphore())
