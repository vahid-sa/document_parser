"""تست پایپ‌لاین PDF: ترتیب، جداکننده، skip، fail-fast، سقف هم‌زمانی، گاردها."""

import asyncio
import threading

import httpx
import pytest
from openai import APIConnectionError

from document_parser.analyzer import Decision, PageAnalysis
from document_parser.configs import get_settings
from document_parser.exceptions import (
    DocumentCorruptError,
    LLMProviderError,
    PageLimitExceededError,
)
from document_parser.models import PageMethod
from document_parser.ocr import OCRParser
from document_parser.pdf_convertor import PDFConverter
from document_parser.pdf_pipeline import PDFPipeline
from tests.conftest import FakeCompletions, make_completion, make_encrypted_pdf, make_pdf


def conn_error() -> APIConnectionError:
    return APIConnectionError(message="boom", request=httpx.Request("POST", "http://t"))


# متن لاتین → arabic_ratio صفر → تصمیم OCR (رفتار عمدی checker برای اسناد غیرفارسی)
async def test_pages_ordered_and_joined(ocr_parser, pdf_converter, fake_completions):
    # سمافور ۱ → نگاشت قطعی پاسخ→صفحه (تست ترتیب، نه هم‌زمانی)
    fake_completions.responses = [
        make_completion("MD 0"),
        make_completion("MD 1"),
        make_completion("MD 2"),
    ]
    pipeline = PDFPipeline(
        pdf_converter=pdf_converter,
        ocr_parser=ocr_parser,
        page_semaphore=asyncio.Semaphore(1),
        docling_lock=threading.Lock(),
    )
    result = await pipeline.run(make_pdf(["Alpha", "Beta", "Gamma"]))
    assert result.markdown == "MD 0\n\n---\n\nMD 1\n\n---\n\nMD 2"
    assert [p.page for p in result.pages] == [1, 2, 3]
    assert all(p.method == PageMethod.ocr for p in result.pages)
    assert result.total_tokens_used == 90


# async def test_empty_page_is_skipped_without_llm_call(pdf_pipeline, fake_completions):
#     fake_completions.responses = [make_completion("A"), make_completion("B")]
#     result = await pdf_pipeline.run(make_pdf(["Alpha", "", "Gamma"]))
#     assert result.markdown == "A\n\n---\n\nB"
#     assert [p.method for p in result.pages] == [
#         PageMethod.ocr,
#         PageMethod.empty,
#         PageMethod.ocr,
#     ]
#     assert len(fake_completions.calls) == 2


async def test_corrupt_pdf_raises(pdf_pipeline):
    with pytest.raises(DocumentCorruptError):
        await pdf_pipeline.run(b"garbage bytes not a pdf")


async def test_encrypted_pdf_raises(pdf_pipeline):
    with pytest.raises(DocumentCorruptError):
        await pdf_pipeline.run(make_encrypted_pdf())


async def test_page_limit_exceeded(pdf_pipeline, monkeypatch):
    monkeypatch.setenv("PARSER_MAX_PDF_PAGES", "2")
    get_settings.cache_clear()
    try:
        with pytest.raises(PageLimitExceededError):
            await pdf_pipeline.run(make_pdf(["A", "B", "C"]))
    finally:
        monkeypatch.delenv("PARSER_MAX_PDF_PAGES")
        get_settings.cache_clear()


async def test_fail_fast_cancels_remaining_pages(fake_client):
    # سمافور ۱ → ترتیب اجرا تضمین‌شده:
    # صفحهٔ ۱: موفق (۱ فراخوانی)؛ صفحهٔ ۲: ۳ تلاش retry همه fail → سند fail؛
    # صفحهٔ ۳: توسط TaskGroup کنسل می‌شود و هرگز صدا زده نمی‌شود.
    fake_client.chat.completions.responses = [
        make_completion("ok"),
        conn_error(),
        conn_error(),
        conn_error(),
    ]
    pipeline = PDFPipeline(
        pdf_converter=PDFConverter(),
        ocr_parser=OCRParser(fake_client, "test-ocr-model"),
        page_semaphore=asyncio.Semaphore(1),
        docling_lock=threading.Lock(),
    )
    with pytest.raises(LLMProviderError):
        await pipeline.run(make_pdf(["A", "B", "C"]))
    # ۱ (صفحهٔ ۱) + ۳ (retry صفحهٔ ۲) = ۴؛ صفحهٔ ۳ اضافه نمی‌شود
    assert len(fake_client.chat.completions.calls) == 4


async def test_semaphore_bounds_concurrency(fake_client):
    completions = FakeCompletions(
        responses=[make_completion(f"page {i}") for i in range(6)],
        delay=0.05,
    )
    fake_client.chat.completions = completions
    pipeline = PDFPipeline(
        pdf_converter=PDFConverter(),
        ocr_parser=OCRParser(fake_client, "test-ocr-model"),
        page_semaphore=asyncio.Semaphore(2),
        docling_lock=threading.Lock(),
    )
    result = await pipeline.run(make_pdf(["A", "B", "C", "D", "E", "F"]))
    assert completions.max_concurrent == 2
    assert result.markdown.count("---") == 5  # ۶ صفحه → ۵ جداکننده


@pytest.mark.slow
async def test_docling_path_used_when_analyzer_forces_convert(
    fake_completions, ocr_parser, pdf_converter
):
    class ForceConvertAnalyzer:
        def analyze(self, page):
            return PageAnalysis(decision=Decision.CONVERT)

    pipeline = PDFPipeline(
        pdf_converter=pdf_converter,
        ocr_parser=ocr_parser,
        page_semaphore=asyncio.Semaphore(2),
        docling_lock=threading.Lock(),
        analyzer=ForceConvertAnalyzer(),
    )
    result = await pipeline.run(make_pdf(["Hello Docling"]))
    assert result.pages[0].method == PageMethod.docling
    assert "Hello" in result.markdown
    assert len(fake_completions.calls) == 0  # LLM هرگز صدا زده نشد
