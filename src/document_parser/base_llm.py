"""کلاینت LLM پایه با retry و backoff نمایی (۲**attempt)."""

import asyncio
import logging
from abc import ABC
from typing import Dict, List, Optional, Union

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    OpenAIError,
)
from openai.types.chat import ChatCompletion

from .configs import get_settings
from .exceptions import InternalParseError, LLMProviderError

logger = logging.getLogger(__name__)

# خطاهای شبکه/API که retry می‌شوند (OpenAIError والد همهٔ آن‌هاست).
_RETRYABLE_ERRORS = (APIError, APIConnectionError, APITimeoutError, APIStatusError, OpenAIError)


class BaseLLm(ABC):
    def __init__(self, client: AsyncOpenAI, model_id: str, system_prompt: Optional[str] = None):
        self.MODEL_ID = model_id
        self.SYSTEM_PROMPT = system_prompt
        self._client = client

    async def chat(
        self,
        user_content: List[Dict[str, Union[str, Dict[str, str]]]],
        **kwargs,
    ) -> ChatCompletion:
        """فراخوانی مدل؛ در صورت شکست تا ``PARSER_LLM_MAX_RETRIES`` بار تلاش می‌شود.

        خطای غیرمنتظرهٔ خودمان → ``InternalParseError`` (۵۰۰).
        شکست نهایی بعد از retry → ``LLMProviderError`` (۵۰۲).
        """
        settings = get_settings()
        max_attempts = max(1, settings.PARSER_LLM_MAX_RETRIES)

        messages = []
        if self.SYSTEM_PROMPT is not None:
            messages.append({"role": "system", "content": self.SYSTEM_PROMPT})
        messages.append({"role": "user", "content": user_content})

        last_error: Optional[Exception] = None
        for attempt in range(max_attempts):
            try:
                response = await self._client.chat.completions.create(
                    messages=messages,
                    model=self.MODEL_ID,
                    **kwargs,
                )
                return response
            except _RETRYABLE_ERRORS as e:
                last_error = e
                logger.warning(
                    "LLM call failed",
                    extra={
                        "model": self.MODEL_ID,
                        "attempt": attempt + 1,
                        "max_attempts": max_attempts,
                        "error": str(e),
                    },
                )
                if attempt == max_attempts - 1:
                    break
                await asyncio.sleep(2**attempt)
            except Exception as e:
                logger.exception("unexpected error during LLM call")
                raise InternalParseError(
                    f"unexpected error during LLM call: {e}"
                ) from e

        raise LLMProviderError(
            f"LLM call failed after {max_attempts} attempt(s); "
            f"model: {self.MODEL_ID}; last error: {last_error}"
        )

    async def assert_api_ready(self) -> None:
        """موجود بودن مدل روی endpoint را چک می‌کند (برای readyz و startup)."""
        models = await self._client.models.list()
        available = any(model.id == self.MODEL_ID for model in models.data)
        if not available:
            raise AssertionError(
                f"model {self.MODEL_ID} does not exist in {self._client.base_url}"
            )
