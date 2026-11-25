"""CLI برای اجرای client-side.

مثال:
    document-parser inputs/hesab.pdf -o out.md --stats stats.json
    python -m document_parser inputs/hesab.pdf --json -

Exit codes:
    0 → موفق
    2 → خطای فایل ورودی (معادل ۴xx در API)
    1 → خطای داخلی/LLM (معادل ۵xx در API)
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

from .exceptions import ClientDocumentError, ParserError
from .models import DocumentResult
from .runtime import build_runtime

logger = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="document-parser",
        description="Convert documents (PDF/image) to Markdown.",
    )
    parser.add_argument("file", type=Path, help="input document (PDF or image)")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="write markdown to this file (default: stdout)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        metavar="STATS_PATH",
        help="write stats JSON to this path ('-' means stdout)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="enable debug logs"
    )
    return parser


async def _run_pipeline(content: bytes) -> DocumentResult:
    runtime = build_runtime()
    try:
        # چک آماده‌بودن endpoint — فقط هشدار، جریان را قطع نمی‌کند.
        try:
            await runtime.ocr_parser.assert_api_ready()
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM endpoint not ready: %s", e)
        return await runtime.document_pipeline.run(content)
    finally:
        await runtime.aclose()


def _stats_payload(result: DocumentResult) -> dict:
    return {
        "num_pages": len(result.pages),
        "pages": [p.model_dump(exclude={"markdown"}) for p in result.pages],
        "total_tokens_used": result.total_tokens_used,
        "avg_latency_ms": result.avg_latency_ms,
    }


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        content = args.file.read_bytes()
    except OSError as e:
        print(f"error: cannot read file: {e}", file=sys.stderr)
        return 2

    try:
        result = asyncio.run(_run_pipeline(content))
    except ClientDocumentError as e:
        print(f"error [{e.code}]: {e.message}", file=sys.stderr)
        return 2
    except ParserError as e:
        print(f"error [{e.code}]: {e.message}", file=sys.stderr)
        return 1
    except Exception as e:  # pragma: no cover - safety net
        print(f"unexpected error: {e}", file=sys.stderr)
        return 1

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result.markdown, encoding="utf-8")
        print(f"markdown saved to {args.output}", file=sys.stderr)
    else:
        print(result.markdown)

    if args.json is not None:
        stats = json.dumps(_stats_payload(result), indent=2, ensure_ascii=False)
        if str(args.json) == "-":
            print(stats)
        else:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(stats + "\n", encoding="utf-8")
            print(f"stats saved to {args.json}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
