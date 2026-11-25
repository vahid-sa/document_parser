import logging
from PIL import Image
from abc import ABC
from openai import AsyncOpenAI, APIConnectionError, APIStatusError, APITimeoutError, APIError, OpenAIError
from openai.types.chat import ChatCompletion
from functools import wraps
from typing import Optional, Union, List, Dict

from .utils import image_to_url


logger = logging.getLogger(__name__)


def log_openai_error(func):

    @wraps(func)
    async def wrapper(*args, **kwargs):
        e = None
        try:
            ret = await func(*args, **kwargs)
        except (APIError, APIConnectionError, APITimeoutError, APIStatusError) as e:
            log = f"form: OpenAI API, message: {e.message}, base_url: {e.request.url}, method: {e.request.method}"
            if e.type is not None:
                log += f", type: {e.type}"
            if e.code is not None:
                log += f", code: {e.code}"
            if e.param is not None:
                log += f", param: {e.param}"
            logger.exception(log)
            raise
        except OpenAIError as e:
            logger.exception(f"from OpenAIError, message: {e}")
            raise
        except Exception as e:
            logger.exception(f"from OpenAI Exception, message: {e}")
            raise
        return ret

    return wrapper


class BaseLLm(ABC):
    def __init__(self, client: AsyncOpenAI, model_id: str, system_prompt: Optional[str] = None):
        self.MODEL_ID = model_id
        self.SYSTEM_PROMPT = system_prompt
        self._client = client

    @log_openai_error
    async def chat(self, user_content: List[Dict[str, Union[str, Dict[str, str]]]], **kwargs) -> ChatCompletion:
        messages = []
        if self.SYSTEM_PROMPT is not None:
            messages.append(
                {
                    "role": "system",
                    "content": self.SYSTEM_PROMPT,
                },
            )
        messages.append(
            {
                "role": "user",
                "content": user_content
            }
        )
        response = await self._client.chat.completions.create(messages=messages, model=self.MODEL_ID, **kwargs)
        return response

    @log_openai_error
    async def assert_api_ready(self):
        models = await self._client.models.list()
        available = any(model.id == self.MODEL_ID for model in models.data)
        if not available:
            log = f"model {self.MODEL_ID} does not exist in {self._client.base_url}"
            raise AssertionError(log)
