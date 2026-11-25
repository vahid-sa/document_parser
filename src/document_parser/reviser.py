from typing import Optional

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from .base_llm import BaseLLm


class Reviser(BaseLLm):
    """اصلاح/بازبینی متن با LLM.

    این قابلیت فعلاً در فلو استفاده نمی‌شود ولی ساخته می‌شود و آمادهٔ اتصال است
    (مثلاً ترکیب خروجی OCR و docling برای اصلاح خطاها در آینده).
    """

    def __init__(self, client: AsyncOpenAI, model_id: str, system_prompt: Optional[str] = None):
        super().__init__(client, model_id, system_prompt)

    async def chat(self, user_prompt: str, **kwargs) -> ChatCompletion:
        user_content = [
            {
                "type": "text",
                "text": user_prompt,
            }
        ]
        response = await super().chat(user_content=user_content, **kwargs)
        return response
