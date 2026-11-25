"""تست لایه LLM: retry/backoff، پرامپت، خروجی خالی، assert_api_ready."""

import asyncio

import httpx
import pytest
from openai import APIConnectionError
from PIL import Image

from document_parser.configs import get_settings
from document_parser.exceptions import LLMProviderError
from document_parser.ocr import OCRParser
from tests.conftest import FakeAsyncOpenAI, FakeCompletions, make_completion

IMAGE = Image.new("RGB", (10, 10), "red")


def conn_error() -> APIConnectionError:
    return APIConnectionError(message="boom", request=httpx.Request("POST", "http://t"))


@pytest.fixture(autouse=True)
def _fast_sleep(monkeypatch):
    async def fake_sleep(delay: float):
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)


async def test_extract_text_returns_markdown_and_tokens(ocr_parser, fake_completions):
    fake_completions.responses = [make_completion("  Hello MD  ")]
    out = await ocr_parser.extract_text(IMAGE)
    assert out.markdown == "Hello MD"
    assert out.tokens_used == 30
    assert out.latency_ms >= 0


async def test_extract_text_uses_settings_prompt(ocr_parser, fake_completions):
    fake_completions.responses = [make_completion("ok")]
    await ocr_parser.extract_text(IMAGE)
    call = fake_completions.calls[0]
    user_message = call["messages"][-1]
    text_part = next(p for p in user_message["content"] if p["type"] == "text")
    assert text_part["text"] == get_settings().LLM_OCR_PROMPT
    image_part = next(p for p in user_message["content"] if p["type"] == "image_url")
    assert image_part["image_url"]["url"].startswith("data:image/")
    assert image_part["image_url"]["detail"] == "high"


async def test_extract_text_custom_prompt(ocr_parser, fake_completions):
    fake_completions.responses = [make_completion("ok")]
    await ocr_parser.extract_text(IMAGE, prompt="custom prompt")
    user_message = fake_completions.calls[0]["messages"][-1]
    text_part = next(p for p in user_message["content"] if p["type"] == "text")
    assert text_part["text"] == "custom prompt"


async def test_retry_then_success(ocr_parser, fake_completions):
    fake_completions.responses = [
        conn_error(),
        conn_error(),
        make_completion("recovered"),
    ]
    out = await ocr_parser.extract_text(IMAGE)
    assert out.markdown == "recovered"
    assert len(fake_completions.calls) == 3


async def test_all_retries_fail(ocr_parser, fake_completions):
    fake_completions.responses = [conn_error(), conn_error(), conn_error()]
    with pytest.raises(LLMProviderError):
        await ocr_parser.extract_text(IMAGE)
    assert len(fake_completions.calls) == 3  # PARSER_LLM_MAX_RETRIES پیش‌فرض


async def test_empty_response_raises(ocr_parser, fake_completions):
    fake_completions.responses = [make_completion("   ")]
    with pytest.raises(LLMProviderError):
        await ocr_parser.extract_text(IMAGE)


async def test_reviser_chat_is_async(reviser, fake_completions):
    fake_completions.responses = [make_completion("revised text")]
    response = await reviser.chat("fix this")
    assert response.choices[0].message.content == "revised text"
    user_message = fake_completions.calls[0]["messages"][0]
    assert user_message["role"] == "user"
    assert user_message["content"][0]["text"] == "fix this"


async def test_assert_api_ready_ok(ocr_parser):
    await ocr_parser.assert_api_ready()  # نباید خطا بدهد


async def test_assert_api_ready_unknown_model():
    completions = FakeCompletions()
    client = FakeAsyncOpenAI(completions, model_ids=("other-model",))
    ocr = OCRParser(client, "missing-model")
    with pytest.raises(AssertionError):
        await ocr.assert_api_ready()
