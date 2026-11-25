from functools import cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from enum import StrEnum


class MIMEType(StrEnum):
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
    LLM_BASE_URL: str
    LLM_API_KEY: str

    LLM_REVISER: str
    LLM_OCR: str

    PDF_PAGE_TO_IMAGE_SCALE: float

@cache
def get_settings() -> Settings:
    return Settings()
