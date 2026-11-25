"""FastAPI router برای اجرای server-side و integrate با پروژه‌های دیگر.

اجرای مستقل:
    uvicorn document_parser.api:create_app --factory

Integrate در پروژهٔ دیگر (روش پیشنهادی — با lifespan مشترک):
    from fastapi import FastAPI
    from document_parser.api import parser_lifespan, router

    app = FastAPI(lifespan=parser_lifespan)
    app.include_router(router, prefix="/parser", tags=["parser"])

اگر پروژهٔ میزبان از ``parser_lifespan`` استفاده نکند، runtime به‌صورت lazy
ساخته می‌شود (اولین request) و ``aclose_global_runtime`` برای shutdown اختیاری است.

قرارداد خطا (۴xx = تقصیر فایل، ۵xx = تقصیر ما):
    {"detail": {"code": "...", "message": "...", "page": null}}
"""

import base64
import binascii
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.routing import APIRouter
from pydantic import BaseModel

from .configs import get_settings
from .exceptions import ClientDocumentError, FileTooLargeError, ParserError
from .models import DocumentResult, ErrorInfo
from .runtime import ParserRuntime, build_runtime

logger = logging.getLogger(__name__)

router = APIRouter(tags=["document-parser"])

_global_runtime: Optional[ParserRuntime] = None


@asynccontextmanager
async def parser_lifespan(app: FastAPI):
    """lifespan آماده برای compose در FastAPI میزبان."""
    runtime = build_runtime()
    app.state.parser_runtime = runtime
    try:
        yield
    finally:
        await runtime.aclose()


async def aclose_global_runtime() -> None:
    """بستن runtimeِ lazy (برای shutdown پروژهٔ میزبان، اختیاری)."""
    global _global_runtime
    if _global_runtime is not None:
        await _global_runtime.aclose()
        _global_runtime = None


async def _get_or_build_global_runtime() -> ParserRuntime:
    global _global_runtime
    if _global_runtime is None:
        _global_runtime = build_runtime()
    return _global_runtime


async def _get_runtime(request: Request) -> ParserRuntime:
    runtime = getattr(request.app.state, "parser_runtime", None)
    if runtime is not None:
        return runtime
    return await _get_or_build_global_runtime()


def _to_http_error(e: ParserError) -> HTTPException:
    info = ErrorInfo(code=e.code, message=e.message, page=e.page)
    return HTTPException(
        status_code=e.http_status,
        detail=info.model_dump(exclude_none=True),
    )


async def _parse_content(request: Request, content: bytes) -> DocumentResult:
    if not content:
        raise _to_http_error(ClientDocumentError("empty file."))
    runtime = await _get_runtime(request)
    try:
        return await runtime.document_pipeline.run(content)
    except ParserError as e:
        logger.error("parse failed [%s]: %s", e.code, e.message)
        raise _to_http_error(e) from None


class ParseB64Request(BaseModel):
    content_b64: str
    filename: Optional[str] = None


@router.post(
    "/parse",
    response_model=DocumentResult,
    summary="Convert an uploaded document to Markdown",
)
async def parse_document(request: Request, file: UploadFile = File(...)) -> DocumentResult:
    settings = get_settings()
    max_bytes = settings.PARSER_MAX_FILE_SIZE_MB * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise _to_http_error(
            FileTooLargeError(
                f"file exceeds limit of {settings.PARSER_MAX_FILE_SIZE_MB} MB."
            )
        )
    return await _parse_content(request, content)


@router.post(
    "/parse-b64",
    response_model=DocumentResult,
    summary="Convert a base64-encoded document to Markdown",
)
async def parse_document_b64(request: Request, body: ParseB64Request) -> DocumentResult:
    try:
        content = base64.b64decode(body.content_b64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise _to_http_error(
            ClientDocumentError(f"invalid base64 content: {e}")
        ) from None
    return await _parse_content(request, content)


@router.get("/healthz", summary="Liveness probe")
async def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz", summary="Readiness probe (checks LLM endpoint)")
async def readyz(request: Request) -> dict:
    runtime = await _get_runtime(request)
    try:
        await runtime.assert_ready()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail={"code": "not_ready", "message": str(e)},
        ) from None
    return {"status": "ready"}


def create_app(runtime: Optional[ParserRuntime] = None) -> FastAPI:
    """اپ مستقل؛ ``runtime`` اختیاری برای تزریق (تست/integration)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.parser_runtime = (
            runtime if runtime is not None else build_runtime()
        )
        try:
            yield
        finally:
            await app.state.parser_runtime.aclose()

    app = FastAPI(
        title="document-parser",
        description="Document (PDF/image) to Markdown parser",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app
