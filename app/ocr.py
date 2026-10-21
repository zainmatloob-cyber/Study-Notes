"""Tesseract OCR helpers. Degrades gracefully when Tesseract is not installed."""
import io
import shutil
from pathlib import Path

from PIL import Image

from . import config

try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None

_available: bool | None = None


def ocr_available() -> bool:
    global _available
    if _available is None:
        if pytesseract is None:
            _available = False
        else:
            if Path(config.TESSERACT_CMD).exists():
                pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD
            elif shutil.which("tesseract"):
                pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract")
            try:
                pytesseract.get_tesseract_version()
                _available = True
            except Exception:
                _available = False
    return _available


def ocr_image(image: Image.Image) -> str:
    if not ocr_available():
        return ""
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    return pytesseract.image_to_string(image, lang=config.OCR_LANG).strip()


def ocr_image_bytes(data: bytes) -> str:
    return ocr_image(Image.open(io.BytesIO(data)))


def ocr_pdf_page(page) -> str:
    """OCR a PyMuPDF page by rendering it at 300 DPI."""
    if not ocr_available():
        return ""
    pix = page.get_pixmap(dpi=300)
    return ocr_image_bytes(pix.tobytes("png"))
