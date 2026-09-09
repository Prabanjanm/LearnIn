"""
Deep PDF validation - stage 1 of the pipeline.

Runs *after* core/upload_policy.py has already checked extension, MIME,
size and magic bytes. That check proves the bytes start with "%PDF-"; this
one proves the document is actually usable: openable, not password
protected, and not devoid of pages.

Everything here raises a single `PdfValidationError` whose message is safe
to show to the admin verbatim.
"""
import logging

# PyMuPDF 1.28 deprecated the legacy top-level `fitz` alias in favour of
# `pymupdf`; aliasing keeps the familiar name without the deprecation warning.
import pymupdf as fitz

logger = logging.getLogger(__name__)


class PdfValidationError(Exception):
    """Message is admin-facing. Never put a traceback in it."""


def open_pdf(content: bytes) -> "fitz.Document":
    """
    Opens the bytes as a PDF or raises PdfValidationError. Callers are
    responsible for closing the returned document.
    """
    if not content:
        raise PdfValidationError(
            "The uploaded file is empty. Please upload the PDF again."
        )

    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception:
        # The underlying MuPDF error text is not something an admin can act
        # on, and can echo file internals - log it, show a plain message.
        logger.exception("Failed to open uploaded PDF")
        raise PdfValidationError(
            "This PDF appears to be corrupted and could not be opened. "
            "Try re-downloading it from the source and uploading again."
        )

    return document


def validate_pdf(content: bytes) -> dict:
    """
    Validates the uploaded source PDF.

    Returns a small summary dict ({"page_count": int, "has_text_layer":
    bool}) on success; raises PdfValidationError on any rejection.
    """
    document = open_pdf(content)

    try:
        # Password protection: we refuse, we never attempt to crack it.
        if document.needs_pass or document.is_encrypted:
            raise PdfValidationError(
                "This PDF is password protected. Please upload an unlocked "
                "copy - LearnIn will not attempt to bypass the password."
            )

        page_count = document.page_count

        if page_count == 0:
            raise PdfValidationError(
                "This PDF has no pages. Please check the file and upload again."
            )

        has_text = False
        has_any_content = False

        for page in document:
            try:
                text = page.get_text().strip()
                drawings = page.get_images(full=True)
            except Exception:
                logger.exception("Failed to read page content during validation")
                raise PdfValidationError(
                    "This PDF could not be read past page 1 and looks damaged. "
                    "Try re-downloading it from the source."
                )

            if text:
                has_text = True
                has_any_content = True
            elif drawings:
                has_any_content = True

        if not has_any_content:
            # No text anywhere AND no images anywhere: there is nothing an
            # OCR pass could rescue either.
            raise PdfValidationError(
                "This PDF has pages but no readable content at all "
                "(no text and no images). Please upload the real question paper."
            )

        return {"page_count": page_count, "has_text_layer": has_text}

    finally:
        document.close()
