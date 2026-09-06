"""
PDF type detection - stage 3 of the pipeline.

Decides whether the document carries a real text layer (extractable
directly) or is a scan (needs OCR). The answer is stored on the job and
shown to the admin verbatim - "PDF Type: Scanned - OCR Required" is
information the reviewer needs, not an implementation detail to log away.
"""
import logging

# PyMuPDF 1.28 deprecated the legacy top-level `fitz` alias in favour of
# `pymupdf`; aliasing keeps the familiar name without the deprecation warning.
import pymupdf as fitz

from app.core.enums import PdfTypeEnum

logger = logging.getLogger(__name__)

# A page with fewer than this many extractable characters is treated as
# having no usable text layer. Scanned pages usually yield 0; a stray
# stamped page number or OCR-hint artifact can yield a handful, which is
# why the bar is not simply "> 0".
MIN_CHARS_PER_TEXT_PAGE = 60

# Share of pages that must have a usable text layer for the whole document
# to count as TEXT. A text-based paper with a couple of full-page scanned
# figures should still be treated as TEXT.
TEXT_PAGE_RATIO = 0.5


def analyze_pdf(content: bytes) -> dict:
    """
    Returns {"pdf_type": PdfTypeEnum, "page_count": int,
             "text_pages": int, "total_chars": int}.

    Never raises for content reasons - an unreadable document comes back as
    UNKNOWN so the caller decides what that means.
    """
    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception:
        logger.exception("PDF analysis could not open the document")
        return {
            "pdf_type": PdfTypeEnum.UNKNOWN,
            "page_count": 0,
            "text_pages": 0,
            "total_chars": 0,
        }

    try:
        page_count = document.page_count

        if page_count == 0:
            return {
                "pdf_type": PdfTypeEnum.UNKNOWN,
                "page_count": 0,
                "text_pages": 0,
                "total_chars": 0,
            }

        text_pages = 0
        total_chars = 0

        for page in document:
            try:
                text = page.get_text().strip()
            except Exception:
                logger.exception("Could not extract text while analysing a page")
                text = ""

            total_chars += len(text)

            if len(text) >= MIN_CHARS_PER_TEXT_PAGE:
                text_pages += 1

        pdf_type = (
            PdfTypeEnum.TEXT
            if text_pages >= max(1, round(page_count * TEXT_PAGE_RATIO))
            else PdfTypeEnum.SCANNED
        )

        return {
            "pdf_type": pdf_type,
            "page_count": page_count,
            "text_pages": text_pages,
            "total_chars": total_chars,
        }

    finally:
        document.close()


PDF_TYPE_LABELS = {
    PdfTypeEnum.TEXT: "Text-based",
    PdfTypeEnum.SCANNED: "Scanned - OCR Required",
    PdfTypeEnum.UNKNOWN: "Unknown",
}


def pdf_type_label(pdf_type: PdfTypeEnum | None) -> str:
    if pdf_type is None:
        return "Not analysed yet"
    return PDF_TYPE_LABELS.get(pdf_type, "Unknown")
