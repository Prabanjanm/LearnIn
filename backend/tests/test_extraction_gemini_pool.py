"""
Coverage for the Gemini-based OCR path in
app/modules/paper_processing/extraction.py: page-order preservation across
the thread pool (same guarantee as the pytesseract path,
tests/test_extraction_ocr_pool.py), the page-level PositionedBlock shape,
error surfacing, and the Gemini-vs-pytesseract dispatch rule in
extract_text/extract_text_with_positions.

Never calls the real Gemini API - get_gemini_client() is monkeypatched with
a fake, exactly like FakeDriveClient stands in for the real Drive service.
"""
import time

import pymupdf
import pytest

from app.core.config import settings
from app.core.enums import PdfTypeEnum
from app.modules.paper_processing import extraction


class FakeGeminiClient:
    def __init__(self, extract_text_from_image):
        self._extract_text_from_image = extract_text_from_image

    def extract_text_from_image(self, image_bytes, mime_type="image/png"):
        return self._extract_text_from_image(image_bytes)


def _solid_color_pdf(colors) -> bytes:
    document = pymupdf.open()
    for color in colors:
        page = document.new_page()
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10))
        pixmap.set_rect(pixmap.irect, color)
        page.insert_image(page.rect, pixmap=pixmap)
    content = document.tobytes()
    document.close()
    return content


def _average_channel(image_bytes: bytes) -> int:
    import io
    from PIL import Image
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return image.getpixel((5, 5))[0]


@pytest.fixture(autouse=True)
def _gemini_key(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")


def test_gemini_page_order_is_preserved_even_when_pages_finish_out_of_order(monkeypatch):
    colors = [(10, 10, 10), (100, 100, 100), (220, 220, 220)]
    content = _solid_color_pdf(colors)
    delay_by_channel = {10: 0.15, 100: 0.05, 220: 0.0}

    def fake_extract(image_bytes):
        channel = _average_channel(image_bytes)
        time.sleep(delay_by_channel[channel])
        return f"page-r{channel}"

    monkeypatch.setattr(
        extraction, "get_gemini_client", lambda: FakeGeminiClient(fake_extract)
    )

    text = extraction.extract_with_gemini(content)
    pages = text.split(extraction.PAGE_BREAK_MARKER)

    assert pages == ["page-r10", "page-r100", "page-r220"]


def test_gemini_with_positions_returns_one_block_per_page(monkeypatch):
    colors = [(10, 10, 10), (100, 100, 100), (220, 220, 220)]
    content = _solid_color_pdf(colors)
    label_by_channel = {10: "first page text", 100: "second page text", 220: "third page text"}

    monkeypatch.setattr(
        extraction, "get_gemini_client",
        lambda: FakeGeminiClient(lambda img: label_by_channel[_average_channel(img)]),
    )

    text, blocks = extraction.extract_with_gemini_with_positions(content)

    assert [b.page_number for b in blocks] == [0, 1, 2]
    assert "first page text" in text
    assert "second page text" in text
    assert "third page text" in text
    # One block per page, spanning the whole page rect.
    document = pymupdf.open(stream=content, filetype="pdf")
    for i, block in enumerate(blocks):
        page_rect = document[i].rect
        assert block.bbox == (page_rect.x0, page_rect.y0, page_rect.x1, page_rect.y1)
    document.close()


def test_gemini_blank_page_produces_no_block_but_does_not_fail(monkeypatch):
    content = _solid_color_pdf([(10, 10, 10), (100, 100, 100)])

    monkeypatch.setattr(
        extraction, "get_gemini_client",
        lambda: FakeGeminiClient(lambda img: "" if _average_channel(img) == 100 else "some text"),
    )

    text, blocks = extraction.extract_with_gemini_with_positions(content)
    assert len(blocks) == 1
    assert blocks[0].page_number == 0


def test_gemini_request_failure_surfaces_as_ocr_unavailable(monkeypatch):
    content = _solid_color_pdf([(10, 10, 10)])

    def boom(image_bytes):
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(extraction, "get_gemini_client", lambda: FakeGeminiClient(boom))

    with pytest.raises(extraction.OcrUnavailableError):
        extraction.extract_with_gemini(content)


def test_missing_gemini_api_key_surfaces_as_ocr_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    content = _solid_color_pdf([(10, 10, 10)])

    with pytest.raises(extraction.OcrUnavailableError):
        # get_gemini_client() is the real one here - GeminiClient.client
        # raises GeminiConfigError itself when no key is configured.
        extraction.extract_with_gemini(content)


# --------------------------------------------------- dispatch rule tests --

def test_extract_text_prefers_gemini_when_key_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        extraction, "get_gemini_client",
        lambda: FakeGeminiClient(lambda img: "from gemini"),
    )

    content = _solid_color_pdf([(10, 10, 10)])
    text, ocr_used = extraction.extract_text(content, PdfTypeEnum.SCANNED)

    assert ocr_used is True
    assert "from gemini" in text


def test_extract_text_falls_back_to_tesseract_when_no_key_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)

    called = {"gemini": False}

    def fail_if_called():
        called["gemini"] = True
        raise AssertionError("Gemini should not be used when no key is configured")

    monkeypatch.setattr(extraction, "get_gemini_client", fail_if_called)

    content = _solid_color_pdf([(10, 10, 10)])
    with pytest.raises(extraction.OcrUnavailableError):
        # pytesseract isn't installed in this dev environment - the
        # fallback path itself fails, but the point is it never reaches
        # for Gemini first.
        extraction.extract_text(content, PdfTypeEnum.SCANNED)

    assert called["gemini"] is False
