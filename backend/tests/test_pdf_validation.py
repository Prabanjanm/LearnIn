import pytest

from app.modules.paper_processing.pdf_validation import (
    PdfValidationError,
    validate_pdf,
)

from pdf_fixtures import (  # noqa: E402 - tests/ is on sys.path via pytest rootdir
    blank_pages_pdf,
    corrupted_pdf,
    empty_pdf,
    encrypted_pdf,
    sample_paper_pdf,
    scanned_pdf,
)


def test_valid_text_pdf_passes():
    result = validate_pdf(sample_paper_pdf())

    assert result["page_count"] == 2
    assert result["has_text_layer"] is True


def test_scanned_pdf_passes_validation_without_a_text_layer():
    # A scan is a perfectly valid source - it just needs OCR later.
    result = validate_pdf(scanned_pdf(page_count=2))

    assert result["page_count"] == 2
    assert result["has_text_layer"] is False


def test_corrupted_pdf_is_rejected():
    with pytest.raises(PdfValidationError) as exc:
        validate_pdf(corrupted_pdf())

    assert "corrupted" in str(exc.value).lower()


def test_encrypted_pdf_is_rejected_not_cracked():
    with pytest.raises(PdfValidationError) as exc:
        validate_pdf(encrypted_pdf())

    message = str(exc.value).lower()
    assert "password" in message
    assert "bypass" in message


def test_zero_page_pdf_is_rejected():
    with pytest.raises(PdfValidationError) as exc:
        validate_pdf(empty_pdf())

    assert "no pages" in str(exc.value).lower()


def test_pdf_with_only_blank_pages_is_rejected():
    with pytest.raises(PdfValidationError) as exc:
        validate_pdf(blank_pages_pdf())

    assert "no readable content" in str(exc.value).lower()


def test_empty_bytes_are_rejected():
    with pytest.raises(PdfValidationError):
        validate_pdf(b"")
