"""تست API: قرارداد موفق/خطا، سرور مستقل و integrate با include_router."""

import asyncio
import base64
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from document_parser.api import create_app, router
from document_parser.configs import get_settings
from document_parser.document_pipeline import DocumentPipeline
from document_parser.image_pipeline import ImagePipeline
from document_parser.ocr import OCRParser
from document_parser.pdf_convertor import PDFConverter
from document_parser.pdf_pipeline import PDFPipeline
from document_parser.reviser import Reviser
from document_parser.runtime import ParserRuntime
from tests.conftest import FakeAsyncOpenAI, FakeCompletions, make_completion, make_pdf


@pytest.fixture
def client(runtime):
    app = create_app(runtime=runtime)
    with TestClient(app) as test_client:
        yield test_client


def test_parse_pdf_returns_document_result(client, fake_completions):
    # هر دو صفحه پاسخ یکسان می‌گیرند تا نتیجه مستقل از ترتیبِ هم‌زمان باشد
    fake_completions.responses = [make_completion("MD"), make_completion("MD")]
    response = client.post(
        "/parse", files={"file": ("doc.pdf", make_pdf(["Alpha", "Beta"]), "application/pdf")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["markdown"] == "MD\n\n---\n\nMD"
    assert data["total_tokens_used"] == 60
    assert len(data["pages"]) == 2
    assert data["pages"][0]["page"] == 1
    assert data["pages"][1]["page"] == 2


def test_parse_unsupported_mime_returns_415(client):
    response = client.post(
        "/parse", files={"file": ("doc.txt", b"plain text", "text/plain")}
    )
    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "unsupported_mime_type"


def test_parse_too_large_returns_413(client, monkeypatch):
    monkeypatch.setenv("PARSER_MAX_FILE_SIZE_MB", "0")
    get_settings.cache_clear()
    try:
        response = client.post(
            "/parse", files={"file": ("doc.pdf", make_pdf(["A"]), "application/pdf")}
        )
        assert response.status_code == 413
        assert response.json()["detail"]["code"] == "file_too_large"
    finally:
        monkeypatch.delenv("PARSER_MAX_FILE_SIZE_MB")
        get_settings.cache_clear()


def test_parse_b64_roundtrip(client, fake_completions):
    fake_completions.responses = [make_completion("B64 MD")]
    payload = {
        "content_b64": base64.b64encode(make_pdf(["Alpha"])).decode(),
        "filename": "x.pdf",
    }
    response = client.post("/parse-b64", json=payload)
    assert response.status_code == 200
    assert response.json()["markdown"] == "B64 MD"


def test_parse_b64_invalid_returns_422(client):
    response = client.post("/parse-b64", json={"content_b64": "!!!not-base64!!!"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "client_document_error"


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_ok(client):
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readyz_not_ready_returns_503():
    completions = FakeCompletions()
    fake_client = FakeAsyncOpenAI(completions, model_ids=("unknown-model",))
    ocr = OCRParser(fake_client, "test-ocr-model")
    reviser = Reviser(fake_client, "test-reviser-model")
    pdf_pipeline = PDFPipeline(
        pdf_converter=PDFConverter(),
        ocr_parser=ocr,
        page_semaphore=asyncio.Semaphore(2),
        docling_lock=threading.Lock(),
    )
    runtime = ParserRuntime(
        document_pipeline=DocumentPipeline(pdf_pipeline, ImagePipeline(ocr)),
        ocr_parser=ocr,
        reviser=reviser,
        client=fake_client,
        page_semaphore=pdf_pipeline._page_semaphore,
        docling_lock=pdf_pipeline._docling_lock,
    )
    app = create_app(runtime=runtime)
    with TestClient(app) as test_client:
        response = test_client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "not_ready"


def test_include_router_integration(runtime, fake_completions):
    """پروژهٔ میزبان فقط router را include می‌کند (بدون lifespan ما)."""
    fake_completions.responses = [make_completion("HOST MD")]
    host = FastAPI()
    host.include_router(router, prefix="/parser")
    host.state.parser_runtime = runtime

    with TestClient(host) as host_client:
        response = host_client.post(
            "/parser/parse",
            files={"file": ("doc.pdf", make_pdf(["A"]), "application/pdf")},
        )
    assert response.status_code == 200
    assert response.json()["markdown"] == "HOST MD"


def test_empty_upload_returns_422(client):
    response = client.post("/parse", files={"file": ("doc.pdf", b"", "application/pdf")})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "client_document_error"
