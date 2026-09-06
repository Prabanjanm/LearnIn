from app.core.enums import PdfTypeEnum, WatermarkStatusEnum
from app.modules.paper_processing.extraction import (
    PAGE_BREAK_MARKER,
    extract_text_layer,
)
from app.modules.paper_processing.pdf_analysis import analyze_pdf, pdf_type_label
from app.modules.paper_processing.watermark import clean_watermarks

from pdf_fixtures import (  # noqa: E402 - tests/ is on sys.path via pytest rootdir
    sample_paper_pdf,
    scanned_pdf,
    text_pdf,
    watermarked_pdf,
)


def test_text_layer_pdf_is_classified_as_text():
    analysis = analyze_pdf(sample_paper_pdf())

    assert analysis["pdf_type"] == PdfTypeEnum.TEXT
    assert analysis["page_count"] == 2
    assert analysis["text_pages"] == 2
    assert pdf_type_label(analysis["pdf_type"]) == "Text-based"


def test_image_only_pdf_is_classified_as_scanned():
    analysis = analyze_pdf(scanned_pdf(page_count=3))

    assert analysis["pdf_type"] == PdfTypeEnum.SCANNED
    assert analysis["text_pages"] == 0
    assert pdf_type_label(analysis["pdf_type"]) == "Scanned - OCR Required"


def test_unreadable_bytes_are_unknown_not_a_crash():
    analysis = analyze_pdf(b"not a pdf at all")

    assert analysis["pdf_type"] == PdfTypeEnum.UNKNOWN


def test_text_extraction_keeps_a_page_break_marker_between_pages():
    text = extract_text_layer(sample_paper_pdf())

    assert PAGE_BREAK_MARKER in text
    assert "binary search" in text
    assert "stable sorting algorithm" in text


def test_clean_pdf_needs_no_watermark_work():
    result = clean_watermarks(text_pdf([
        "1. Only question?\nA) a\nB) b\nC) c\nD) d",
        "2. Another one?\nA) e\nB) f\nC) g\nD) h",
    ]))

    assert result.status == WatermarkStatusEnum.NOT_NEEDED
    assert result.content is None


def test_known_source_watermark_is_removed_and_question_text_survives():
    result = clean_watermarks(watermarked_pdf(pages=3))

    assert result.status == WatermarkStatusEnum.CLEANED
    assert result.content is not None
    assert any("example-papers" in text for text in result.removed_texts)

    cleaned_text = extract_text_layer(result.content)
    assert "example-papers.com" not in cleaned_text
    # The real content is untouched - removal is span-scoped, never
    # page-scoped.
    assert "Genuine question number 1" in cleaned_text
