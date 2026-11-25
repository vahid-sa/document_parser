"""تبدیل PDF به Markdown با docling (بدون OCR داخلی؛ OCR با LLM انجام می‌شود)."""

import io

from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import (
    ConversionError,
    DocumentConverter,
    PdfFormatOption,
)

from .base_converter import BaseConverter
from .exceptions import ConversionFailedError, InternalParseError


class PDFConverter(BaseConverter):
    def __init__(self):
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        pipeline_options.do_table_structure = True
        pipeline_options.table_structure_options.do_cell_matching = True
        self.__converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                )
            }
        )

    def convert_to_markdown(self, content: bytes, page_number: int) -> str:
        """صفحهٔ ``page_number`` (۰-مبنا) را تبدیل می‌کند.

        ``ConversionError`` از خود docling معمولاً یعنی ساختار فایل مشکل دارد → ۴۲۲.
        بقیهٔ خطاهای غیرمنتظره → ``InternalParseError`` (۵۰۰).
        """
        stream = DocumentStream(
            name="document.pdf",
            stream=io.BytesIO(content),
        )
        n = page_number + 1
        try:
            result = self.__converter.convert(stream, page_range=(n, n))
            markdown = result.document.export_to_markdown()
        except ConversionError as e:
            raise ConversionFailedError(
                f"docling failed to convert page {page_number + 1}: {e}",
                page=page_number + 1,
            ) from e
        except Exception as e:
            raise InternalParseError(
                f"unexpected error while converting page {page_number + 1}: {e}",
                page=page_number + 1,
            ) from e
        return markdown
