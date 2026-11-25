import io
import base64
from typing import Tuple
from PIL import Image


def get_image_format_and_mime(image: Image.Image) -> Tuple[str, str]:
    DEFAULT_FORMAT = "PNG"
    DEFAULT_MIME_TYPE = "image/png"
    format = DEFAULT_FORMAT
    mime = DEFAULT_MIME_TYPE
    image_format = image.format
    if image_format is not None:
        image_mime = Image.MIME.get(image_format)
        if image_mime is not None:
            format = image_format
            mime = image_mime
    return format, mime


def image_to_url(image: Image.Image) -> str:
    if image.mode not in ("RGB", "RGBA", "L"):
        image = image.convert("RGB")
    image_format, mime_type = get_image_format_and_mime(image)
    buffer = io.BytesIO()
    image.save(buffer, format=image_format)
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    image_url = f"data:{mime_type};base64,{encoded}"
    return image_url


def is_persian_alphabet_script(ch: str) -> bool:
    """حروف فارسی و عربی، به‌اضافهٔ صورت‌های نمایشی آن‌ها."""
    cp = ord(ch)
    return (
        0x0600 <= cp <= 0x06FF
        or 0x0750 <= cp <= 0x077F
        or 0x08A0 <= cp <= 0x08FF
        or 0xFB50 <= cp <= 0xFDFF
        or 0xFE70 <= cp <= 0xFEFF
    )
