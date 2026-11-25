from openai import AsyncOpenAI
from typing import Optional
from PIL import Image
from openai.types.chat import ChatCompletion

from .base_llm import BaseLLm
from .utils import image_to_url


class OCRParser(BaseLLm):
    def __init__(self, client: AsyncOpenAI, model_id: str, system_prompt: Optional[str] = None):
        super().__init__(client, model_id, system_prompt)

    async def chat(self, image: Image.Image, user_prompt: Optional[str] = None, **kwargs) -> ChatCompletion:
        user_content = []
        if user_prompt is not None:
            user_content.append(
                {
                    "type": "text",
                    "text": user_prompt,
                }
            )
        user_content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": image_to_url(image)
                }
            }
        )
        response = await super().chat(user_content=user_content, **kwargs)
        return response
