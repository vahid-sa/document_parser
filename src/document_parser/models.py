"""مدل‌های خروجی مشترک بین CLI و API."""

from enum import StrEnum
from typing import List, Optional

from pydantic import BaseModel, Field


class PageMethod(StrEnum):
    """روش پردازش هر صفحه."""

    docling = "docling"
    ocr = "ocr"
    empty = "empty"


class OCROutput(BaseModel):
    """خروجی یک فراخوانی OCR."""

    markdown: str
    tokens_used: int = 0
    latency_ms: float = 0.0


class PageResult(BaseModel):
    """نتیجهٔ پردازش یک صفحه."""

    page: int = Field(..., ge=1, description="شمارهٔ صفحه (۱-مبنا)")
    method: PageMethod = Field(..., description="مسیر پردازش صفحه")
    markdown: str = ""
    tokens_used: int = 0
    latency_ms: float = 0.0


class DocumentResult(BaseModel):
    """نتیجهٔ نهایی تبدیل یک سند."""

    markdown: str
    pages: List[PageResult] = Field(default_factory=list)
    total_tokens_used: int = 0
    avg_latency_ms: float = 0.0


class ErrorInfo(BaseModel):
    """قرارداد خطا برای مصرف‌کننده‌های API."""

    code: str
    message: str
    page: Optional[int] = None


class ErrorResponse(BaseModel):
    error: ErrorInfo
