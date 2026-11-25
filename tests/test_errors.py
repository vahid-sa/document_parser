"""تست تاکسونومی خطا: نگاشت کلاس → HTTP status."""

import pytest

from document_parser.exceptions import (
    ClientDocumentError,
    ConversionFailedError,
    DocumentCorruptError,
    FileTooLargeError,
    InternalParseError,
    LLMProviderError,
    PageLimitExceededError,
    ParserError,
    UnsupportedMIMEError,
)


@pytest.mark.parametrize(
    "exc,expected_status",
    [
        (UnsupportedMIMEError("x"), 415),
        (FileTooLargeError("x"), 413),
        (PageLimitExceededError("x"), 422),
        (DocumentCorruptError("x"), 422),
        (ConversionFailedError("x"), 422),
        (ClientDocumentError("x"), 422),
        (LLMProviderError("x"), 502),
        (InternalParseError("x"), 500),
    ],
)
def test_http_status_mapping(exc, expected_status):
    assert exc.http_status == expected_status


def test_all_subclass_parser_error():
    for exc in (
        UnsupportedMIMEError,
        FileTooLargeError,
        PageLimitExceededError,
        DocumentCorruptError,
        ConversionFailedError,
        LLMProviderError,
        InternalParseError,
    ):
        assert issubclass(exc, ParserError)


def test_page_attribute_optional():
    e = ConversionFailedError("bad page", page=3)
    assert e.page == 3
    assert e.message == "bad page"

    e2 = ConversionFailedError("no page")
    assert e2.page is None


def test_error_codes_unique():
    classes = [
        UnsupportedMIMEError,
        FileTooLargeError,
        PageLimitExceededError,
        DocumentCorruptError,
        ConversionFailedError,
        LLMProviderError,
        InternalParseError,
    ]
    codes = [c("x").code for c in classes]
    assert len(codes) == len(set(codes))
