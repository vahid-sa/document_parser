from enum import StrEnum
from functools import cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class MIMEType(StrEnum):
    """فرمت‌های پشتیبانی‌شدهٔ فعلی (PDF و تصویر) و آینده (excel/docx)."""

    pdf = "application/pdf"
    jpg = "image/jpeg"
    png = "image/png"
    webp = "image/webp"
    heic = "image/heic"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "PDF_PARSER"
    APP_VERSION: str = "1.0.0"

    # ---- LLM endpoint (OpenAI-compatible) ----
    LLM_BASE_URL: str
    LLM_API_KEY: str

    LLM_REVISER: str
    LLM_OCR: str

    # ---- PDF ----
    PDF_PAGE_TO_IMAGE_SCALE: float = 2.0

    # ---- محدودیت‌ها و پارامترهای parser ----
    PARSER_MAX_PDF_PAGES: int = 50
    PARSER_MAX_CONCURRENT_PAGES: int = 8
    PARSER_MAX_FILE_SIZE_MB: int = 20
    PARSER_LLM_MAX_RETRIES: int = 3
    PARSER_LLM_TIMEOUT_SECONDS: float = 120.0

    # ---- پرامپت‌ها ----
    LLM_OCR_PROMPT: str = "OCR. Extract text and layout from the image."


@cache
def get_settings() -> Settings:
    return Settings()
