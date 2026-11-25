"""تست CLI: exit codes و خروجی‌ها (با runtime فیک)."""

import json

import pytest

from document_parser import cli
from tests.conftest import make_completion, make_pdf


@pytest.fixture
def patched_runtime(monkeypatch, runtime):
    monkeypatch.setattr(cli, "build_runtime", lambda: runtime)
    return runtime


def test_missing_file_returns_2(tmp_path):
    assert cli.main([str(tmp_path / "nope.pdf")]) == 2


def test_successful_run_writes_markdown_and_stats(
    tmp_path, patched_runtime, fake_completions
):
    fake_completions.responses = [make_completion("CLI MD")]
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(make_pdf(["Alpha"]))

    out = tmp_path / "out.md"
    stats = tmp_path / "stats.json"
    exit_code = cli.main([str(pdf), "-o", str(out), "--json", str(stats)])

    assert exit_code == 0
    assert out.read_text(encoding="utf-8") == "CLI MD"
    payload = json.loads(stats.read_text(encoding="utf-8"))
    assert payload["num_pages"] == 1
    assert payload["pages"][0]["method"] == "ocr"
    assert payload["total_tokens_used"] == 30


def test_markdown_to_stdout_by_default(
    tmp_path, patched_runtime, fake_completions, capsys
):
    fake_completions.responses = [make_completion("STDOUT MD")]
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(make_pdf(["Alpha"]))
    assert cli.main([str(pdf)]) == 0
    assert "STDOUT MD" in capsys.readouterr().out


def test_client_document_error_returns_2(
    tmp_path, patched_runtime, monkeypatch
):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"this is not a real pdf")
    assert cli.main([str(pdf)]) == 2
