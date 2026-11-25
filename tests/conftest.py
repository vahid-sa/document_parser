"""فیکسچرهای مشترک: PDF مصنوعی، کلاینت LLM فیک، runtime فیک.

envها قبل از اولین فراخوانی get_settings تنظیم می‌شوند تا به .env واقعی
وابسته نباشیم؛ برای override در تست‌ها: monkeypatch.setenv + get_settings.cache_clear().
"""

import asyncio
import io
import os
import threading

os.environ.setdefault("LLM_BASE_URL", "http://test.local/v1")
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("LLM_OCR", "test-ocr-model")
os.environ.setdefault("LLM_REVISER", "test-reviser-model")
os.environ.setdefault("PDF_PAGE_TO_IMAGE_SCALE", "2.0")
os.environ.setdefault("PARSER_MAX_PDF_PAGES", "50")
os.environ.setdefault("PARSER_MAX_CONCURRENT_PAGES", "8")
os.environ.setdefault("PARSER_MAX_FILE_SIZE_MB", "20")
os.environ.setdefault("PARSER_LLM_MAX_RETRIES", "3")
os.environ.setdefault("PARSER_LLM_TIMEOUT_SECONDS", "5")

import pymupdf  # noqa: E402
import pytest  # noqa: E402
from openai.types import CompletionUsage  # noqa: E402
from openai.types.chat import (  # noqa: E402
    ChatCompletion,
    ChatCompletionMessage,
)
from openai.types.chat.chat_completion import Choice  # noqa: E402
from PIL import Image  # noqa: E402

from document_parser.configs import get_settings  # noqa: E402
from document_parser.document_pipeline import DocumentPipeline  # noqa: E402
from document_parser.image_pipeline import ImagePipeline  # noqa: E402
from document_parser.ocr import OCRParser  # noqa: E402
from document_parser.pdf_convertor import PDFConverter  # noqa: E402
from document_parser.pdf_pipeline import PDFPipeline  # noqa: E402
from document_parser.reviser import Reviser  # noqa: E402
from document_parser.runtime import ParserRuntime  # noqa: E402

get_settings.cache_clear()


# ---------------------------------------------------------------------------
# سازنده‌های سند مصنوعی
# ---------------------------------------------------------------------------


def make_completion(
    text: str, prompt_tokens: int = 10, completion_tokens: int = 20
) -> ChatCompletion:
    return ChatCompletion(
        id="chatcmpl-test",
        object="chat.completion",
        created=0,
        model="test-ocr-model",
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(role="assistant", content=text),
                finish_reason="stop",
            )
        ],
        usage=CompletionUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


def _png_bytes(width: int = 16, height: int = 16) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "red").save(buffer, format="PNG")
    return buffer.getvalue()


def make_pdf(pages: list) -> bytes:
    """PDF مصنوعی؛ هر عضو: متن (str) یا "image" یا "" (صفحهٔ خالی)."""
    doc = pymupdf.open()
    png = _png_bytes()
    for spec in pages:
        page = doc.new_page()
        if spec == "image":
            page.insert_image(page.rect, stream=png)
        elif spec:
            page.insert_text((72, 100), str(spec), fontname="helv", fontsize=12)
    return doc.tobytes()


def make_encrypted_pdf() -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    return doc.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="user"
    )


# ---------------------------------------------------------------------------
# کلاینت LLM فیک
# ---------------------------------------------------------------------------


class FakeCompletions:
    """chat.completions فیک.

    ``responses`` می‌تواند شامل ChatCompletion یا Exception باشد.
    ``delay`` برای تست هم‌زمانی؛ ``max_concurrent`` بیشینهٔ هم‌زمانی create را ردیابی می‌کند.
    """

    def __init__(self, responses=None, delay: float = 0.0):
        self.responses = list(responses or [])
        self.delay = delay
        self.calls: list[dict] = []
        self.max_concurrent = 0
        self._active = 0

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        self._active += 1
        self.max_concurrent = max(self.max_concurrent, self._active)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            item = (
                self.responses.pop(0)
                if self.responses
                else make_completion("default response")
            )
            if isinstance(item, Exception):
                raise item
            return item
        finally:
            self._active -= 1


class FakeModelList:
    def __init__(self, model_ids):
        self.data = [type("Model", (), {"id": mid})() for mid in model_ids]


class FakeModelsNamespace:
    def __init__(self, model_ids):
        self._model_list = FakeModelList(model_ids)

    async def list(self):
        return self._model_list


class FakeChatNamespace:
    def __init__(self, completions: FakeCompletions):
        self.completions = completions


class FakeAsyncOpenAI:
    def __init__(
        self,
        completions: FakeCompletions,
        model_ids=("test-ocr-model", "test-reviser-model"),
    ):
        self.chat = FakeChatNamespace(completions)
        self.models = FakeModelsNamespace(model_ids)
        self.base_url = "http://test.local/v1"
        self.closed = False

    async def close(self):
        self.closed = True


# ---------------------------------------------------------------------------
# فیکسچرها
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_completions() -> FakeCompletions:
    return FakeCompletions()


@pytest.fixture
def fake_client(fake_completions) -> FakeAsyncOpenAI:
    return FakeAsyncOpenAI(fake_completions)


@pytest.fixture
def ocr_parser(fake_client) -> OCRParser:
    return OCRParser(fake_client, "test-ocr-model")


@pytest.fixture
def reviser(fake_client) -> Reviser:
    return Reviser(fake_client, "test-reviser-model")


@pytest.fixture
def pdf_converter() -> PDFConverter:
    return PDFConverter()


@pytest.fixture
def pdf_pipeline(ocr_parser, pdf_converter) -> PDFPipeline:
    return PDFPipeline(
        pdf_converter=pdf_converter,
        ocr_parser=ocr_parser,
        page_semaphore=asyncio.Semaphore(8),
        docling_lock=threading.Lock(),
    )


@pytest.fixture
def image_pipeline(ocr_parser) -> ImagePipeline:
    return ImagePipeline(ocr_parser)


@pytest.fixture
def runtime(fake_client, ocr_parser, reviser, pdf_pipeline, image_pipeline) -> ParserRuntime:
    return ParserRuntime(
        document_pipeline=DocumentPipeline(pdf_pipeline, image_pipeline),
        ocr_parser=ocr_parser,
        reviser=reviser,
        client=fake_client,
        page_semaphore=pdf_pipeline._page_semaphore,
        docling_lock=pdf_pipeline._docling_lock,
    )
