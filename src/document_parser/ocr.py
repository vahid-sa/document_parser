"""OCR دیداری با LLM."""

import asyncio
import time
from typing import Optional

from PIL import Image
from openai import AsyncOpenAI

from .base_llm import BaseLLm
from .configs import get_settings
from .exceptions import LLMProviderError
from .models import OCROutput
from .utils import image_to_url, preprocess_image


class OCRParser(BaseLLm):
    def __init__(self, client: AsyncOpenAI, model_id: str, system_prompt: Optional[str] = None):
        super().__init__(client, model_id, system_prompt)

    async def extract_text(self, image: Image.Image, prompt: Optional[str] = None) -> OCROutput:
        """تصویر را OCR می‌کند و متن + آمار برمی‌گرداند.

        پیش‌پردازش و encode تصویر (CPU) داخل ``to_thread`` اجرا می‌شود تا
        event loop آزاد بماند.
        """
        settings = get_settings()
        user_prompt = prompt or settings.LLM_OCR_PROMPT

        image = await asyncio.to_thread(preprocess_image, image)
        image_url = await asyncio.to_thread(image_to_url, image)

        user_content = [
            {
                "type": "text",
                "text": user_prompt,
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": image_url,
                    "detail": "high",
                },
            },
        ]

        start = time.perf_counter()
        response = await super().chat(user_content=user_content)
        latency_ms = (time.perf_counter() - start) * 1000

        content = (
            response.choices[0].message.content if response.choices else None
        )
        text = (content or "").strip()
        if not text:
            raise LLMProviderError(
                f"OCR model returned empty response; model: {self.MODEL_ID}"
            )

        usage = response.usage
        tokens_used = (
            usage.prompt_tokens + usage.completion_tokens if usage is not None else 0
        )
        return OCROutput(
            markdown=text,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )
