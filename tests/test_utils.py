from PIL import Image

from document_parser.utils import (
    image_to_url,
    is_persian_alphabet_script,
    preprocess_image,
)


def test_preprocess_returns_rgb_same_size():
    image = Image.new("RGBA", (40, 20), (255, 0, 0, 255))
    out = preprocess_image(image)
    assert out.size == (40, 20)
    assert out.mode == "RGB"


def test_preprocess_grayscales():
    image = Image.new("RGB", (10, 10), (255, 0, 0))
    out = preprocess_image(image)
    r, g, b = out.getpixel((5, 5))
    # بعد از L → RGB باید کانال‌ها برابر باشند
    assert r == g == b


def test_image_to_url_data_url_prefix():
    image = Image.new("RGB", (5, 5), "blue")
    url = image_to_url(image)
    assert url.startswith("data:image/")
    assert ";base64," in url


def test_is_persian_alphabet_script():
    assert is_persian_alphabet_script("ا") is True
    assert is_persian_alphabet_script("ی") is True
    assert is_persian_alphabet_script("ك") is True  # کافی عربی
    assert is_persian_alphabet_script("A") is False
    assert is_persian_alphabet_script("1") is False
    assert is_persian_alphabet_script("\u200c") is False  # نیم‌فاصله
