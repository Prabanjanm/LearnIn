"""
Coverage for the thread-pool parallelization of per-page OCR added to
app/modules/paper_processing/extraction.py: pages must come back in their
original order regardless of which one finishes OCR first, and a failure on
any page must still surface exactly like the old serial loop did.

`pytesseract` is not installed in this dev environment (extraction.py lazily
imports it and treats that as OcrUnavailableError, by design) - these tests
inject a fake module into sys.modules instead of needing the real package or
a tesseract binary, so they exercise the real thread-pool code path.
"""
import sys
import time
import types

import pymupdf
import pytest

from app.modules.paper_processing import extraction


class FakeTesseractNotFoundError(Exception):
    pass


def _install_fake_pytesseract(monkeypatch, image_to_string=None, image_to_data=None):
    fake = types.ModuleType("pytesseract")
    fake.TesseractNotFoundError = FakeTesseractNotFoundError
    if image_to_string is not None:
        fake.image_to_string = image_to_string
    if image_to_data is not None:
        fake.image_to_data = image_to_data
        fake.Output = types.SimpleNamespace(DICT="dict")
    monkeypatch.setitem(sys.modules, "pytesseract", fake)


def _solid_color_pdf(colors) -> bytes:
    """One page per color, each page filled edge-to-edge so any sampled
    pixel of the rendered raster reliably reflects that page's color."""
    document = pymupdf.open()
    for color in colors:
        page = document.new_page()
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10))
        pixmap.set_rect(pixmap.irect, color)
        page.insert_image(page.rect, pixmap=pixmap)
    content = document.tobytes()
    document.close()
    return content


def _red_channel(image):
    return image.convert("RGB").getpixel((5, 5))[0]


def test_ocr_page_order_is_preserved_even_when_pages_finish_out_of_order(monkeypatch):
    # Page 0 (darkest) is made the slowest to "OCR", page 2 (lightest) the
    # fastest - if results were collected by completion order instead of
    # submission order, the joined text would come back scrambled.
    colors = [(10, 10, 10), (100, 100, 100), (220, 220, 220)]
    content = _solid_color_pdf(colors)
    delay_by_red = {10: 0.15, 100: 0.05, 220: 0.0}

    def fake_image_to_string(image, *args, **kwargs):
        red = _red_channel(image)
        time.sleep(delay_by_red[red])
        return f"page-r{red}"

    _install_fake_pytesseract(monkeypatch, image_to_string=fake_image_to_string)

    text = extraction.extract_with_ocr(content)
    pages = text.split(extraction.PAGE_BREAK_MARKER)

    assert pages == ["page-r10", "page-r100", "page-r220"]


def test_ocr_with_positions_page_numbers_stay_in_order_too(monkeypatch):
    colors = [(10, 10, 10), (100, 100, 100), (220, 220, 220)]
    content = _solid_color_pdf(colors)
    delay_by_red = {10: 0.1, 100: 0.0, 220: 0.05}
    label_by_red = {10: "first", 100: "second", 220: "third"}

    def fake_image_to_data(image, *args, output_type=None, **kwargs):
        red = _red_channel(image)
        time.sleep(delay_by_red[red])
        word = label_by_red[red]
        return {
            "text": [word],
            "left": [0], "top": [0], "width": [10], "height": [10],
            "block_num": [1], "par_num": [1], "line_num": [1],
        }

    _install_fake_pytesseract(monkeypatch, image_to_data=fake_image_to_data)

    text, blocks = extraction.extract_with_ocr_with_positions(content)

    assert [b.page_number for b in blocks] == [0, 1, 2]
    assert text.split(extraction.PAGE_BREAK_MARKER.strip())[0].strip() == "first"


def test_a_failing_page_still_surfaces_as_ocr_unavailable(monkeypatch):
    content = _solid_color_pdf([(10, 10, 10), (100, 100, 100)])

    def fake_image_to_string(image, *args, **kwargs):
        if _red_channel(image) == 100:
            raise FakeTesseractNotFoundError()
        return "ok"

    _install_fake_pytesseract(monkeypatch, image_to_string=fake_image_to_string)

    with pytest.raises(extraction.OcrUnavailableError):
        extraction.extract_with_ocr(content)


def test_missing_pytesseract_module_is_a_clean_ocr_unavailable_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "pytesseract", None)

    with pytest.raises(extraction.OcrUnavailableError):
        extraction.extract_with_ocr(_solid_color_pdf([(10, 10, 10)]))
