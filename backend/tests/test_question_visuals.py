"""
Unit tests for the visual (diagram/figure) detection and association module.

Each test builds a small synthetic PDF at test time (no fixture files) and
runs the real position-aware extractor + parser to get real ParsedQuestion/
PositionedBlock inputs, then checks `detect_question_visuals`'s output -
no mocking of PyMuPDF itself, since the geometry it returns is exactly what
this module depends on.
"""
from app.core.enums import ImageSourceType
from app.modules.paper_processing.extraction import extract_text_layer_with_positions
from app.modules.paper_processing.question_parser import parse_questions
from app.modules.paper_processing.question_visuals import detect_question_visuals

from pdf_fixtures import (  # noqa: E402 - tests/ is on sys.path via pytest rootdir
    pdf_with_embedded_diagram,
    pdf_with_unaccounted_gap,
    pdf_with_vector_diagram,
    scanned_pdf,
    text_pdf,
)


def _parse(content: bytes):
    text, blocks = extract_text_layer_with_positions(content)
    parsed = parse_questions(text)
    return parsed, blocks


def test_embedded_image_is_associated_with_the_right_question_only():
    content = pdf_with_embedded_diagram()
    parsed, blocks = _parse(content)
    assert len(parsed) == 2

    visuals = detect_question_visuals(content, parsed, blocks)

    assert 0 in visuals
    assert any(c.source_type == ImageSourceType.EMBEDDED_RASTER for c in visuals[0])
    # The image sits well before question 2 starts - it must not bleed over.
    assert 1 not in visuals


def test_embedded_image_bytes_are_preserved_unmodified():
    content = pdf_with_embedded_diagram()
    parsed, blocks = _parse(content)

    visuals = detect_question_visuals(content, parsed, blocks)
    candidate = next(c for c in visuals[0] if c.source_type == ImageSourceType.EMBEDDED_RASTER)

    assert candidate.image_bytes
    assert candidate.ext in ("png", "jpeg", "jpg")


def test_vector_drawing_is_rendered_and_associated():
    content = pdf_with_vector_diagram()
    parsed, blocks = _parse(content)
    assert len(parsed) == 1

    visuals = detect_question_visuals(content, parsed, blocks)

    assert 0 in visuals
    assert any(c.source_type == ImageSourceType.VECTOR_RENDER for c in visuals[0])
    candidate = next(c for c in visuals[0] if c.source_type == ImageSourceType.VECTOR_RENDER)
    assert candidate.image_bytes  # a real PNG crop, not a description


def test_unaccounted_gap_falls_back_to_region_render():
    content = pdf_with_unaccounted_gap()
    parsed, blocks = _parse(content)
    assert len(parsed) == 1

    visuals = detect_question_visuals(content, parsed, blocks)

    assert 0 in visuals
    assert any(c.source_type == ImageSourceType.REGION_RENDER for c in visuals[0])


def test_ordinary_paragraph_spacing_does_not_trigger_a_false_positive():
    """A normal-looking question with tight, ordinary spacing between its
    text and its options must not get a fabricated "diagram"."""
    content = text_pdf(["1. A perfectly ordinary question?\nA) one\nB) two\nC) three\nD) four"])
    parsed, blocks = _parse(content)

    visuals = detect_question_visuals(content, parsed, blocks)

    assert visuals == {}


def test_whole_page_scan_is_not_treated_as_one_questions_diagram():
    """A full-page scanned image (the entire "page", not a sub-figure) must
    never be silently assigned to a single question as its diagram."""
    content = scanned_pdf(page_count=1)
    # scanned_pdf() has no real text layer; treat the (empty) result as the
    # parser would for a page with no detected questions - detection must
    # not crash or invent an association with nothing to anchor to.
    text, blocks = extract_text_layer_with_positions(content)
    parsed = parse_questions(text)

    visuals = detect_question_visuals(content, parsed, blocks)

    assert visuals == {}


def test_should_stop_halts_before_rendering_further_pages():
    """
    should_stop is checked once per page, before that page's (expensive)
    rendering work starts - a stop requested up front must skip every page,
    and one that flips True partway through must still keep whatever was
    already found for earlier pages.
    """
    import pymupdf

    document = pymupdf.open()
    for i in range(3):
        page = document.new_page()
        page.insert_textbox(
            pymupdf.Rect(40, 40, 555, 90),
            f"{i + 1}. Refer to the diagram below. What shape is shown?",
            fontsize=11, fontname="helv",
        )
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100))
        pixmap.set_rect(pixmap.irect, (10, 10, 200))
        page.insert_image(pymupdf.Rect(220, 110, 340, 230), pixmap=pixmap)
        page.insert_textbox(
            pymupdf.Rect(40, 260, 555, 340),
            "A) circle\nB) square\nC) triangle\nD) hexagon",
            fontsize=11, fontname="helv",
        )
    content = document.tobytes()
    document.close()

    parsed, blocks = _parse(content)
    assert len(parsed) == 3

    # Stops before any page is processed - nothing found at all.
    visuals_none = detect_question_visuals(content, parsed, blocks, should_stop=lambda: True)
    assert visuals_none == {}

    # Never asked to stop - every question gets its diagram.
    visuals_all = detect_question_visuals(content, parsed, blocks, should_stop=lambda: False)
    assert set(visuals_all.keys()) == {0, 1, 2}

    # Stops after the first page - only question 0's diagram (page 0) is
    # found, questions 1 and 2 (later pages) are not reached.
    calls = {"n": 0}

    def stop_after_one_page():
        calls["n"] += 1
        return calls["n"] > 1

    visuals_partial = detect_question_visuals(content, parsed, blocks, should_stop=stop_after_one_page)
    assert 0 in visuals_partial
    assert 1 not in visuals_partial
    assert 2 not in visuals_partial
