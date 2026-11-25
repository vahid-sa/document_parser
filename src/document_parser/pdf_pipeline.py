"""پایپ‌لاین PDF: پردازش موازی صفحه‌ها با تصمیم صفحه‌به‌صفحه.

الگوی هم‌زمانی (برگرفته از other_project):
- ``asyncio.Semaphore`` سراسری برای سقف هم‌زمانی صفحات (بین requestهای API مشترک است).
- هر worker سند pymupdf خودش را از bytes باز می‌کند (thread-safe).
- کارهای CPU (تحلیل/رندر/پیش‌پردازش) با ``asyncio.to_thread``.
- docling با ``threading.Lock`` سریال می‌شود (thread-safety آن تضمین‌شده نیست).
- ``asyncio.TaskGroup`` برای fail-fast: اولین خطا بقیهٔ تسک‌ها را کنسل می‌کند
  (منطبق با سیاست «شکست یک صفحه = شکست کل سند»).

خروجی صفحات با ``\\n\\n---\\n\\n`` join می‌شود.
"""

import asyncio
import logging
import threading
from typing import List, Optional

import pymupdf

from .analyzer import Decision, PageAnalyzer
from .base_pipeline import BasePipeline
from .configs import get_settings
from .exceptions import (
    DocumentCorruptError,
    InternalParseError,
    PageLimitExceededError,
    ParserError,
)
from .models import DocumentResult, PageMethod, PageResult
from .ocr import OCRParser
from .pdf_convertor import PDFConverter

logger = logging.getLogger(__name__)

PAGE_SEPARATOR = "\n\n---\n\n"


class PDFPipeline(BasePipeline):
    def __init__(
        self,
        pdf_converter: PDFConverter,
        ocr_parser: OCRParser,
        page_semaphore: asyncio.Semaphore,
        docling_lock: threading.Lock,
        analyzer: Optional[PageAnalyzer] = None,
    ):
        self._pdf_converter = pdf_converter
        self._ocr_parser = ocr_parser
        self._page_semaphore = page_semaphore
        self._docling_lock = docling_lock
        self._analyzer = analyzer if analyzer is not None else PageAnalyzer()

    async def run(self, content: bytes) -> DocumentResult:
        settings = get_settings()

        total_pages = self._validate_document(content)
        if total_pages > settings.PARSER_MAX_PDF_PAGES:
            raise PageLimitExceededError(
                f"PDF has {total_pages} pages; limit is {settings.PARSER_MAX_PDF_PAGES}."
            )

        results: List[Optional[PageResult]] = [None] * total_pages
        try:
            async with asyncio.TaskGroup() as tg:
                for page_index in range(total_pages):
                    tg.create_task(self._process_page(results, content, page_index))
        except* Exception as eg:
            # اولین ParserError واقعی را منتشر می‌کنیم؛ بقیهٔ خطاها → ۵۰۰.
            for exc in eg.exceptions:
                if isinstance(exc, ParserError):
                    raise exc from None
            raise InternalParseError(
                f"unexpected error while processing PDF: {eg.exceptions[0]}"
            ) from eg

        pages = [p for p in results if p is not None]
        markdown = PAGE_SEPARATOR.join(p.markdown for p in pages if p.markdown)
        total_tokens = sum(p.tokens_used for p in pages)
        latencies = [p.latency_ms for p in pages if p.latency_ms > 0]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

        return DocumentResult(
            markdown=markdown,
            pages=pages,
            total_tokens_used=total_tokens,
            avg_latency_ms=avg_latency,
        )

    # ------------------------------------------------------------------
    # اجزای داخلی
    # ------------------------------------------------------------------

    def _validate_document(self, content: bytes) -> int:
        """بازکردن سند و شمارش صفحات؛ خطا → ``DocumentCorruptError``."""
        try:
            doc = pymupdf.open(stream=content, filetype="pdf")
        except Exception as e:
            raise DocumentCorruptError(f"cannot open PDF: {e}") from e
        with doc:
            if doc.needs_pass:
                raise DocumentCorruptError("PDF is password-protected.")
            total_pages = len(doc)
        if total_pages == 0:
            raise DocumentCorruptError("PDF contains 0 pages.")
        return total_pages

    async def _process_page(
        self,
        results: List[Optional[PageResult]],
        content: bytes,
        page_index: int,
    ) -> None:
        async with self._page_semaphore:
            decision, image = await asyncio.to_thread(
                self._prepare_page, content, page_index
            )

            if decision is Decision.SKIP:
                results[page_index] = PageResult(
                    page=page_index + 1, method=PageMethod.empty
                )
                return

            if decision is Decision.CONVERT:
                markdown = await self._run_docling(content, page_index)
                results[page_index] = PageResult(
                    page=page_index + 1,
                    method=PageMethod.docling,
                    markdown=markdown,
                )
                return

            output = await self._ocr_parser.extract_text(image)
            results[page_index] = PageResult(
                page=page_index + 1,
                method=PageMethod.ocr,
                markdown=output.markdown,
                tokens_used=output.tokens_used,
                latency_ms=output.latency_ms,
            )

    def _prepare_page(self, content: bytes, page_index: int):
        """تحلیل و رندر صفحه؛ سندِ اختصاصی این worker باز می‌شود (thread-safe)."""
        with pymupdf.open(stream=content, filetype="pdf") as doc:
            page = doc[page_index]
            analysis = self._analyzer.analyze(page)
            if analysis.decision is not Decision.OCR:
                return analysis.decision, None
            settings = get_settings()
            scale = settings.PDF_PAGE_TO_IMAGE_SCALE
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
            return Decision.OCR, pixmap.pil_image()

    async def _run_docling(self, content: bytes, page_index: int) -> str:
        def locked_convert() -> str:
            with self._docling_lock:
                return self._pdf_converter.convert_to_markdown(content, page_index)

        return await asyncio.to_thread(locked_convert)
