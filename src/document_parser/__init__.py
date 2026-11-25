"""document_parser: تبدیل اسناد (PDF/تصویر) به Markdown.

PDF: تصمیم صفحه‌به‌صفحه بین docling و OCR با LLM (برای اسناد فارسی).
Image: OCR مستقیم.
"""

from .analyzer import Decision, PageAnalysis, PageAnalyzer
from .configs import MIMEType, Settings, get_settings
from .document_pipeline import DocumentPipeline
from .exceptions import (
    ClientDocumentError,
    ConversionFailedError,
    DocumentCorruptError,
    FileTooLargeError,
    InternalParseError,
    LLMProviderError,
    PageLimitExceededError,
    ParserError,
    UnsupportedMIMEError,
)
from .image_pipeline import ImagePipeline
from .models import DocumentResult, ErrorInfo, ErrorResponse, OCROutput, PageMethod, PageResult
from .ocr import OCRParser
from .pdf_convertor import PDFConverter
from .pdf_pipeline import PDFPipeline
from .reviser import Reviser
from .runtime import ParserRuntime, build_runtime

__version__ = "0.2.0"

__all__ = [
    "Decision",
    "PageAnalysis",
    "PageAnalyzer",
    "MIMEType",
    "Settings",
    "get_settings",
    "DocumentPipeline",
    "ImagePipeline",
    "PDFPipeline",
    "PDFConverter",
    "OCRParser",
    "Reviser",
    "ParserRuntime",
    "build_runtime",
    "DocumentResult",
    "PageResult",
    "PageMethod",
    "OCROutput",
    "ErrorInfo",
    "ErrorResponse",
    "ParserError",
    "ClientDocumentError",
    "UnsupportedMIMEError",
    "FileTooLargeError",
    "PageLimitExceededError",
    "DocumentCorruptError",
    "ConversionFailedError",
    "LLMProviderError",
    "InternalParseError",
    "__version__",
]
