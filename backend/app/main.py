"""FastAPI application factory.

Chạy dev: uvicorn app.main:app --reload
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.modules.auth.router import router as auth_router
from app.modules.billing.router import router as billing_router
from app.modules.contracts.router import router as contracts_router
from app.modules.expenses.router import router as expenses_router
from app.modules.ocr.dependencies import get_ocr_engine
from app.modules.ocr.router import router as ocr_router
from app.modules.properties.router import router as properties_router
from app.shared.exceptions import (
    ConflictError,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidImageError,
    NoReadingDetectedError,
    NotFoundError,
    PermissionDeniedError,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Warm-up model OCR ở background — create_task (không await) nên server
    nhận request ngay lập tức; request OCR đến sớm sẽ tự chờ qua init lock.
    """

    async def _warm_up_ocr() -> None:
        try:
            await asyncio.to_thread(get_ocr_engine().load)
            logger.info("OCR model đã warm-up xong")
        except Exception:
            # Warm-up fail không được giết server — request OCR đầu tiên sẽ thử nạp lại
            logger.exception("Warm-up OCR model thất bại")

    warmup_task = asyncio.create_task(_warm_up_ocr())
    yield
    warmup_task.cancel()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="SmartRoom API",
        version="0.1.0",
        description="Nền tảng quản lý nhà trọ & chia tiền chi tiêu",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        # TODO(deploy): thay bằng domain thật khi lên production
        # 3001: máy dev này có Grafana (dự án cũ) chiếm port 3000 -> Next tự nhảy sang 3001
        allow_origins=["http://localhost:3000", "http://localhost:3001"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router, prefix=settings.api_v1_prefix)
    app.include_router(properties_router, prefix=settings.api_v1_prefix)
    app.include_router(contracts_router, prefix=settings.api_v1_prefix)
    app.include_router(expenses_router, prefix=settings.api_v1_prefix)
    app.include_router(billing_router, prefix=settings.api_v1_prefix)
    app.include_router(ocr_router, prefix=settings.api_v1_prefix)

    # Ánh xạ domain exception -> HTTP status (service layer không import HTTPException)
    @app.exception_handler(NotFoundError)
    async def handle_not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)}
        )

    @app.exception_handler(PermissionDeniedError)
    async def handle_forbidden(_: Request, exc: PermissionDeniedError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)}
        )

    @app.exception_handler(ConflictError)
    async def handle_conflict(_: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)}
        )

    @app.exception_handler(InvalidCredentialsError)
    async def handle_bad_credentials(
        _: Request, exc: InvalidCredentialsError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(EmailAlreadyExistsError)
    async def handle_email_conflict(
        _: Request, exc: EmailAlreadyExistsError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)}
        )

    @app.exception_handler(InvalidImageError)
    async def handle_bad_image(_: Request, exc: InvalidImageError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)}
        )

    @app.exception_handler(NoReadingDetectedError)
    async def handle_no_reading(
        _: Request, exc: NoReadingDetectedError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
