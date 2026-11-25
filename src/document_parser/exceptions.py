"""سلسله‌مراتب خطاهای پروژه و نگاشت آن‌ها به کد HTTP.

قاعدهٔ تصمیم:
- ``ClientDocumentError`` → ۴xx: خودِ فایل ورودی مشکل دارد (خراب، بزرگ، رمزدار و…).
- ``LLMProviderError``   → ۵۰۲: سرویس LLM بعد از retry پاسخ نداد.
- ``InternalParseError`` → ۵۰۰: مشکل از خود ماست (باگ / پیکربندی).
"""

from typing import Optional


class ParserError(Exception):
    """پایهٔ همهٔ خطاهای parser."""

    code: str = "parser_error"
    http_status: int = 500

    def __init__(self, message: str, *, page: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.page = page


# ---------------------------------------------------------------------------
# ۴xx — تقصیر فایل ورودی
# ---------------------------------------------------------------------------


class ClientDocumentError(ParserError):
    """فایل ورودی قابل پردازش نیست."""

    code = "client_document_error"
    http_status = 422


class UnsupportedMIMEError(ClientDocumentError):
    """فرمت فایل پشتیبانی نمی‌شود (مثلاً excel/docx فعلاً)."""

    code = "unsupported_mime_type"
    http_status = 415


class FileTooLargeError(ClientDocumentError):
    """حجم فایل از حد مجاز بیشتر است."""

    code = "file_too_large"
    http_status = 413


class PageLimitExceededError(ClientDocumentError):
    """تعداد صفحات PDF از حد مجاز بیشتر است."""

    code = "page_limit_exceeded"
    http_status = 422


class DocumentCorruptError(ClientDocumentError):
    """سند باز نمی‌شود / رمزدار است / صفر صفحه دارد."""

    code = "document_corrupt"
    http_status = 422


class ConversionFailedError(ClientDocumentError):
    """docling نتوانست سند را تبدیل کند؛ معمولاً یعنی ساختار خود فایل مشکل دارد."""

    code = "conversion_failed"
    http_status = 422


# ---------------------------------------------------------------------------
# ۵xx — تقصیر ما
# ---------------------------------------------------------------------------


class LLMProviderError(ParserError):
    """سرویس LLM بعد از retry + backoff پاسخ نداد یا پاسخ خالی داد."""

    code = "llm_provider_error"
    http_status = 502


class InternalParseError(ParserError):
    """خطای غیرمنتظره در کد خودمان."""

    code = "internal_error"
    http_status = 500
