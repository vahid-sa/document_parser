from abc import ABC, abstractmethod

from .models import DocumentResult


class BasePipeline(ABC):
    """قرارداد مشترک همهٔ پایپ‌لاین‌ها (PDF، Image و فرمت‌های آینده)."""

    @abstractmethod
    async def run(self, content: bytes) -> DocumentResult:
        """سند را پردازش و نتیجهٔ نهایی را برمی‌گرداند."""
        raise NotImplementedError
