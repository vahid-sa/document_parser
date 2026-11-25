"""تست پایپ‌لاین تصویر و روتینگ document_pipeline."""

import io

import pytest
from PIL import Image

from document_parser.exceptions import ClientDocumentError, FileTooLargeError
from document_parser.models import PageMethod
from tests.conftest import make_completion, make_pdf


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "red").save(buffer, format="PNG")
    return buffer.getvalue()


async def test_image_pipeline_runs_ocr(image_pipeline, fake_completions):
    fake_completions.responses = [make_completion("IMAGE TEXT")]
    result = await image_pipeline.run(png_bytes())
    assert result.markdown == "IMAGE TEXT"
    assert result.pages[0].method == PageMethod.ocr
    assert result.pages[0].page == 1
    assert result.total_tokens_used == 30


async def test_image_pipeline_corrupt_image_raises(image_pipeline):
    with pytest.raises(ClientDocumentError):
        await image_pipeline.run(b"definitely not an image")


async def test_document_pipeline_routes_pdf_to_pdf_pipeline(
    runtime, fake_completions
):
    fake_completions.responses = [make_completion("PDF VIA ROUTER")]
    result = await runtime.document_pipeline.run(make_pdf(["Alpha"]))
    assert result.markdown == "PDF VIA ROUTER"


async def test_document_pipeline_routes_image_to_image_pipeline(
    runtime, fake_completions
):
    fake_completions.responses = [make_completion("IMG VIA ROUTER")]
    result = await runtime.document_pipeline.run(png_bytes())
    assert result.markdown == "IMG VIA ROUTER"


async def test_document_pipeline_file_too_large(runtime, monkeypatch):
    monkeypatch.setenv("PARSER_MAX_FILE_SIZE_MB", "0")
    from document_parser.configs import get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(FileTooLargeError):
            await runtime.document_pipeline.run(png_bytes())
    finally:
        monkeypatch.delenv("PARSER_MAX_FILE_SIZE_MB")
        get_settings.cache_clear()
