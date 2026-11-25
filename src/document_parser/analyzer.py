"""تحلیل کیفیت صفحه و تصمیم‌گیری مسیر پردازش.

منطق عیناً از ``pdf_pipeline.check_ocr_and_conversion_needs`` قدیمی (و
``check_ok.py``) آمده است — بدون تغییر رفتاری — ولی به یک کلاس خالص و بدون
side-effect منتقل شده تا قابل تست واحد باشد.

سیگنال‌ها:
- وجود هر تصویر (حتی لوگو) → OCR
- نویسه‌های مشکوک (جایگزین/خصوصی/تعریف‌نشده/کنترلی) → OCR
- پرش ترتیب بلوک‌ها به بالا (> ۲۰pt؛ رایج در جدول‌های RTL) → OCR
- نسبت حروف فارسی/عربی < ۰.۵ → OCR
- صفحهٔ خالی (نه متن، نه تصویر) → SKIP (بدون هزینهٔ LLM)
"""

import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from .utils import is_persian_alphabet_script


class Decision(StrEnum):
    """مسیر پردازش یک صفحه."""

    CONVERT = "convert"  # متن سالم است؛ docling کافی است
    OCR = "ocr"  # متن مشکوک است؛ OCR با LLM
    SKIP = "skip"  # صفحهٔ خالی


@dataclass(frozen=True)
class PageAnalysis:
    decision: Decision
    text_length: int = 0
    block_count: int = 0
    image_count: int = 0
    arabic_ratio: float = 0.0
    latin_ratio: float = 0.0
    suspicious_count: int = 0
    upward_jumps: int = 0


class PageAnalyzer:
    """تحلیل‌گر خالص صفحه؛ هیچ stateای ندارد و thread-safe است."""

    def analyze(self, page) -> PageAnalysis:
        text = page.get_text("text", sort=False)
        images = page.get_images()
        blocks = [
            b
            for b in page.get_text("blocks", sort=False)
            if len(b) >= 7 and b[6] == 0 and b[4].strip()
        ]

        # صفحهٔ خالی: نه متن، نه تصویر → بدون فراخوانی LLM رد می‌شود.
        if not text.strip() and not images:
            return PageAnalysis(decision=Decision.SKIP, text_length=len(text))

        letters = [ch for ch in text if unicodedata.category(ch).startswith("L")]
        arabic_letters = [ch for ch in letters if is_persian_alphabet_script(ch)]
        latin_letters = [
            ch for ch in letters if "LATIN" in unicodedata.name(ch, "")
        ]

        arabic_ratio = len(arabic_letters) / max(len(letters), 1)
        latin_ratio = len(latin_letters) / max(len(letters), 1)

        # نویسه‌های مشکوک؛ نیم‌فاصلهٔ فارسی عمداً در این شمارش نیست.
        suspicious_chars = [
            ch
            for ch in text
            if ch == "\uFFFD"  # نویسهٔ جایگزین
            or unicodedata.category(ch) in {"Co", "Cn"}  # خصوصی یا تعریف‌نشده
            or (
                unicodedata.category(ch) == "Cc"
                and ch not in "\n\r\t"
            )
        ]
        suspicious_chars_ratio = len(suspicious_chars) / max(len(text), 1)

        # تعداد دفعاتی که ترتیب بلوک‌ها از بالا به پایین برمی‌گردد.
        # این فقط هشدار است؛ ستون‌های چندگانه ممکن است چنین پرشی ایجاد کنند.
        upward_jumps = 0
        previous_y = None
        for block in blocks:
            y0 = block[1]
            if previous_y is not None and y0 < previous_y - 20:
                upward_jumps += 1
            previous_y = y0

        do_ocr = False
        do_conversion = True
        if bool(images):
            do_ocr = True
        if suspicious_chars:
            do_ocr = True
        if suspicious_chars_ratio > 0.5:
            do_conversion = False
            do_ocr = True
        if upward_jumps:
            do_ocr = True
        if arabic_ratio < 0.5:
            do_ocr = True
        if do_ocr:
            do_conversion = False

        return PageAnalysis(
            decision=Decision.OCR if do_ocr else Decision.CONVERT,
            text_length=len(text),
            block_count=len(blocks),
            image_count=len(images),
            arabic_ratio=arabic_ratio,
            latin_ratio=latin_ratio,
            suspicious_count=len(suspicious_chars),
            upward_jumps=upward_jumps,
        )
