# document-parser

تبدیل اسناد (**PDF** و **تصویر**) به **Markdown**، با تصمیم هوشمند صفحه‌به‌صفحه برای اسناد فارسی:

- متن سالم → تبدیل ساختاری با **docling** (ارزان)
- متن مشکوک (کاراکتر خراب، رمزگذاری معیوب، صفحه تصویری، جدول RTL به‌هم‌ریخته) → **OCR با LLM دیداری** (پرهزینه)
- صفحه خالی → skip بدون هزینه
- `Reviser` به‌عنوان قابلیت آینده ساخته می‌شود ولی فعلاً در فلو نیست

> excel/docx و… در نقشه‌-roadmap هستند؛ فعلاً خطای `415` می‌دهند.

## معماری

```
bytes ──► DocumentPipeline (MIME با libmagic + سقف حجم)
            ├─ pdf   ──► PDFPipeline
            │            TaskGroup + Semaphore سراسری (صفحات موازی)
            │            هر worker سند خودش را باز می‌کند (thread-safe)
            │            ├─ CONVERT → docling (serialize با threading.Lock)
            │            └─ OCR     → render → preprocess → LLM
            │            join("\n\n---\n\n")
            └─ image ──► ImagePipeline → preprocess → OCR (LLM)
```

خطاها:

| کلاس | HTTP | معنی |
|---|---|---|
| `UnsupportedMIMEError` | 415 | فرمت پشتیبانی نمی‌شود |
| `FileTooLargeError` | 413 | حجم > `PARSER_MAX_FILE_SIZE_MB` |
| `PageLimitExceededError` / `DocumentCorruptError` / `ConversionFailedError` | 422 | فایل خراب/رمزدار/بیش از حد صفحه |
| `LLMProviderError` | 502 | LLM بعد از retry نشد |
| `InternalParseError` | 500 | باگ خودمان |

سیاست خطا: **شکست یک صفحه = شکست کل سند** (fail-fast با `TaskGroup`).

## نصب

```bash
uv sync --inexact          # runtime + dev deps
```

## تنظیمات (`.env`)

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `LLM_BASE_URL` / `LLM_API_KEY` | — | endpoint سازگار با OpenAI |
| `LLM_OCR` / `LLM_REVISER` | — | نام مدل‌ها |
| `PDF_PAGE_TO_IMAGE_SCALE` | `2.0` | مقیاس رندر صفحه برای OCR |
| `PARSER_MAX_PDF_PAGES` | `50` | سقف تعداد صفحات |
| `PARSER_MAX_CONCURRENT_PAGES` | `8` | سقف هم‌زمانی صفحات (سراسری) |
| `PARSER_MAX_FILE_SIZE_MB` | `20` | سقف حجم فایل |
| `PARSER_LLM_MAX_RETRIES` | `3` | تعداد تلاش LLM (backoff: `2**attempt`) |
| `PARSER_LLM_TIMEOUT_SECONDS` | `120` | timeout کلاینت LLM |
| `LLM_OCR_PROMPT` | `OCR. Extract...` | پرامپت OCR |

## CLI (کلاینت)

```bash
document-parser inputs/hesab.pdf -o out.md --stats stats.json
python -m document_parser inputs/hesab.pdf --json -     # فقط آمار در stdout
```

Exit codes: `0` موفق · `2` خطای فایل ورودی · `1` خطای داخلی/LLM.

## API (سرور)

اجرای مستقل:

```bash
uvicorn document_parser.api:create_app --factory --host 0.0.0.0 --port 8000
```

Integrate در پروژهٔ دیگر:

```python
from fastapi import FastAPI
from document_parser.api import parser_lifespan, router

app = FastAPI(lifespan=parser_lifespan)
app.include_router(router, prefix="/parser", tags=["parser"])
```

Endpoints (بدون auth):

- `POST /parser/parse` — multipart (`file`) → `DocumentResult`
- `POST /parser/parse-b64` — JSON `{"content_b64": "..."}` → `DocumentResult`
- `GET /parser/healthz` — زنده بودن
- `GET /parser/readyz` — موجود بودن مدل‌ها روی endpoint

خروجی:

```json
{
  "markdown": "...",
  "pages": [
    {"page": 1, "method": "docling", "markdown": "...", "tokens_used": 0, "latency_ms": 0.0},
    {"page": 2, "method": "ocr", "markdown": "...", "tokens_used": 830, "latency_ms": 4120.5}
  ],
  "total_tokens_used": 830,
  "avg_latency_ms": 4120.5
}
```

قرارداد خطا: `{"detail": {"code": "...", "message": "...", "page": null}}`

## تست

```bash
uv run pytest                       # بدون شبکه (LLM فیک)
uv run pytest -m "not slow"         # بدون docling واقعی
```

## الگوهای به‌کاررفته

- **Strategy/Decision**: `PageAnalyzer` خالص → `Decision.CONVERT/OCR/SKIP`
- **Composition Root**: `build_runtime()` — مشترک بین CLI و API
- **Semaphore سراسری** + `TaskGroup` + `asyncio.to_thread` (الگوی other_project)
- retry + backoff نمایی در `BaseLLm` (بدون fallback پرووایدر — تک‌endpoint)

## اسکریپت‌های ریشه (legacy)

`check_ok.py`، `converter_mu.py`، `convert_with_*.py` آزمایش‌های دورهٔ بنچمارک بودند و به
`src` ربطی ندارند؛ صرفاً برای مرجع نگه داشته شده‌اند.
