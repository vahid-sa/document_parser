"""تست واحد analyzer (بدون شبکه/فایل واقعی؛ صفحهٔ duck-typed)."""

from document_parser.analyzer import Decision, PageAnalyzer


class FakePage:
    """شبیه‌ساز pymupdf.Page فقط تا حد نیاز analyzer."""

    def __init__(self, text="", blocks=None, images=None):
        self._text = text
        self._blocks = blocks if blocks is not None else []
        self._images = images if images is not None else []

    def get_text(self, mode, sort=False):
        if mode == "text":
            return self._text
        if mode == "blocks":
            return self._blocks
        raise ValueError(mode)

    def get_images(self):
        return self._images


def block(y0, text="متن"):
    # (x0, y0, x1, y1, text, block_no, block_type)
    return (0.0, y0, 100.0, y0 + 12.0, text, 0, 0)


PERSIAN_TEXT = "سلام دنیای بزرگ و پر از حروف فارسی " * 10


def test_clean_persian_page_converts():
    blocks = [block(10 + i * 20) for i in range(6)]
    page = FakePage(text=PERSIAN_TEXT, blocks=blocks)
    analysis = PageAnalyzer().analyze(page)
    assert analysis.decision is Decision.CONVERT
    assert analysis.arabic_ratio >= 0.5
    assert analysis.suspicious_count == 0
    assert analysis.upward_jumps == 0


def test_empty_page_is_skipped():
    analysis = PageAnalyzer().analyze(FakePage(text="", blocks=[]))
    assert analysis.decision is Decision.SKIP


def test_any_image_triggers_ocr_even_with_clean_text():
    blocks = [block(10 + i * 20) for i in range(6)]
    page = FakePage(text=PERSIAN_TEXT, blocks=blocks, images=[object()])
    analysis = PageAnalyzer().analyze(page)
    assert analysis.decision is Decision.OCR
    assert analysis.image_count == 1


def test_replacement_char_triggers_ocr():
    text = PERSIAN_TEXT + "\ufffd"
    page = FakePage(text=text, blocks=[block(10), block(30)])
    analysis = PageAnalyzer().analyze(page)
    assert analysis.decision is Decision.OCR
    assert analysis.suspicious_count >= 1


def test_control_char_triggers_ocr():
    text = PERSIAN_TEXT + "\x01"
    page = FakePage(text=text, blocks=[block(10), block(30)])
    analysis = PageAnalyzer().analyze(page)
    assert analysis.decision is Decision.OCR


def test_private_use_char_triggers_ocr():
    # مثل week_metadata.PDF: U+F0AD (Private Use Area)
    text = PERSIAN_TEXT + "\uf0ad"
    page = FakePage(text=text, blocks=[block(10), block(30)])
    analysis = PageAnalyzer().analyze(page)
    assert analysis.decision is Decision.OCR


def test_upward_jumps_trigger_ocr():
    # ترتیب y: 10 → 100 → 20 (پرش به بالا > 20pt؛ الگوی جدول RTL)
    blocks = [block(10), block(100), block(20)]
    page = FakePage(text=PERSIAN_TEXT, blocks=blocks)
    analysis = PageAnalyzer().analyze(page)
    assert analysis.decision is Decision.OCR
    assert analysis.upward_jumps >= 1


def test_latin_page_triggers_ocr():
    text = "Hello world with latin letters only " * 10
    page = FakePage(text=text, blocks=[block(10), block(30)])
    analysis = PageAnalyzer().analyze(page)
    assert analysis.decision is Decision.OCR
    assert analysis.arabic_ratio < 0.5


def test_heavily_corrupted_page_triggers_ocr():
    text = "گ" * 10 + "\ufffd" * 60
    page = FakePage(text=text, blocks=[block(10)])
    analysis = PageAnalyzer().analyze(page)
    assert analysis.decision is Decision.OCR
    assert analysis.suspicious_count == 60


def test_newline_and_tab_are_not_suspicious():
    text = PERSIAN_TEXT + "\n\t\r"
    page = FakePage(text=text, blocks=[block(10), block(30)])
    analysis = PageAnalyzer().analyze(page)
    assert analysis.suspicious_count == 0
    assert analysis.decision is Decision.CONVERT
