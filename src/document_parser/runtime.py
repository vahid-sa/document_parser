"""Composition root: ساخت کل گراف اشیاء، یک‌بار (مشترک بین CLI و API).

سمافور صفحات اینجا ساخته می‌شود و در سطح سرویس **سراسری** است؛ یعنی بین
requestهای هم‌زمانِ API هم تقسیم می‌شود.
"""

import asyncio
import logging
import threading
from dataclasses import dataclass
from typing import Optional

from openai import AsyncOpenAI

from .configs import Settings, get_settings
from .document_pipeline import DocumentPipeline
from .exceptions import InternalParseError
from .image_pipeline import ImagePipeline
from .ocr import OCRParser
from .pdf_convertor import PDFConverter
from .pdf_pipeline import PDFPipeline
from .reviser import Reviser

logger = logging.getLogger(__name__)

_REQUIRED_SETTINGS = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_OCR", "LLM_REVISER")


@dataclass
class ParserRuntime:
    """همهٔ اشیای لازم برای اجرا.

    ``reviser`` ساخته می‌شود ولی فعلاً در فلو نیست (قابلیتِ آینده).
    """

    document_pipeline: DocumentPipeline
    ocr_parser: OCRParser
    reviser: Reviser
    client: AsyncOpenAI
    page_semaphore: asyncio.Semaphore
    docling_lock: threading.Lock

    async def aclose(self) -> None:
        await self.client.close()

    async def assert_ready(self) -> None:
        """چک موجود بودن مدل‌ها روی endpoint (برای readyz)."""
        await self.ocr_parser.assert_api_ready()
        await self.reviser.assert_api_ready()


def build_runtime(settings: Optional[Settings] = None) -> ParserRuntime:
    settings = settings if settings is not None else get_settings()

    missing = [
        name
        for name in _REQUIRED_SETTINGS
        if not getattr(settings, name)
    ]
    if missing:
        raise InternalParseError(
            f"missing/empty settings: {', '.join(missing)}; check your .env"
        )

    client = AsyncOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        timeout=settings.PARSER_LLM_TIMEOUT_SECONDS,
    )

    ocr_parser = OCRParser(client, settings.LLM_OCR)
    reviser = Reviser(client, settings.LLM_REVISER)
    pdf_converter = PDFConverter()

    page_semaphore = asyncio.Semaphore(settings.PARSER_MAX_CONCURRENT_PAGES)
    docling_lock = threading.Lock()

    pdf_pipeline = PDFPipeline(
        pdf_converter=pdf_converter,
        ocr_parser=ocr_parser,
        page_semaphore=page_semaphore,
        docling_lock=docling_lock,
    )
    image_pipeline = ImagePipeline(ocr_parser)

    return ParserRuntime(
        document_pipeline=DocumentPipeline(pdf_pipeline, image_pipeline),
        ocr_parser=ocr_parser,
        reviser=reviser,
        client=client,
        page_semaphore=page_semaphore,
        docling_lock=docling_lock,
    )
