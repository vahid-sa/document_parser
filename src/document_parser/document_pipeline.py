"""نقطهٔ ورود عمومی: تشخیص نوع سند (MIME) و روتینگ به پایپ‌لاین مناسب."""

import logging

import magic

from .base_pipeline import BasePipeline
from .configs import MIMEType, get_settings
from .exceptions import FileTooLargeError, UnsupportedMIMEError
from .image_pipeline import ImagePipeline
from .models import DocumentResult
from .pdf_pipeline import PDFPipeline

logger = logging.getLogger(__name__)


class DocumentPipeline(BasePipeline):
    def __init__(self, pdf_pipeline: PDFPipeline, image_pipeline: ImagePipeline):
        self._pdf_pipeline = pdf_pipeline
        self._image_pipeline = image_pipeline

    def check_document_type(self, content: bytes) -> MIMEType:
        file_mime_type = magic.from_buffer(content, mime=True)
        try:
            return MIMEType(file_mime_type)
        except ValueError:
            logger.error("MIME type is not supported: %s", file_mime_type)
            raise UnsupportedMIMEError(
                f"unsupported MIME type: {file_mime_type}"
            ) from None

    async def run(self, content: bytes) -> DocumentResult:
        settings = get_settings()
        max_bytes = settings.PARSER_MAX_FILE_SIZE_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise FileTooLargeError(
                f"file is {len(content) / (1024 * 1024):.2f} MB; "
                f"limit is {settings.PARSER_MAX_FILE_SIZE_MB} MB."
            )

        mime_type = self.check_document_type(content)
        if mime_type is MIMEType.pdf:
            return await self._pdf_pipeline.run(content)
        # jpg / png / webp / heic
        return await self._image_pipeline.run(content)
