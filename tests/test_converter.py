"""تست تبدیل واقعی docling (کند؛ مارکر slow)."""

import pytest

from document_parser.exceptions import ParserError
from tests.conftest import make_pdf


@pytest.mark.slow
def test_convert_to_markdown_returns_text(pdf_converter):
    content = make_pdf(["Hello Docling World"])
    markdown = pdf_converter.convert_to_markdown(content, 0)
    assert "Hello" in markdown


@pytest.mark.slow
def test_convert_garbage_raises_parser_error(pdf_converter):
    with pytest.raises(ParserError):
        pdf_converter.convert_to_markdown(b"this is not a pdf at all", 0)
