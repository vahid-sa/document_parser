"""پایپ‌لاین تصویر: ورودی مستقیم به OCR (بدون checker)."""

import asyncio
import io
import logging

from PIL import Image, UnidentifiedImageError

from .base_pipeline import BasePipeline
from .exceptions import DocumentCorruptError
from .models import DocumentResult, PageMethod, PageResult
from .ocr import OCRParser

logger = logging.getLogger(__name__)


class ImagePipeline(BasePipeline):
    def __init__(self, ocr_parser: OCRParser):
        self._ocr_parser = ocr_parser

    async def run(self, content: bytes) -> DocumentResult:
        def open_image() -> Image.Image:
            image = Image.open(io.BytesIO(content))
            image.load()  # خطای decode همین‌جا بلند می‌شود
            return image

        try:
            image = await asyncio.to_thread(open_image)
        except UnidentifiedImageError as e:
            raise DocumentCorruptError(f"cannot identify image file: {e}") from e
        except Exception as e:
            raise DocumentCorruptError(f"cannot decode image: {e}") from e

        output = await self._ocr_parser.extract_text(image)
        page = PageResult(
            page=1,
            method=PageMethod.ocr,
            markdown=output.markdown,
            tokens_used=output.tokens_used,
            latency_ms=output.latency_ms,
        )
        return DocumentResult(
            markdown=output.markdown,
            pages=[page],
            total_tokens_used=output.tokens_used,
            avg_latency_ms=output.latency_ms,
        )
