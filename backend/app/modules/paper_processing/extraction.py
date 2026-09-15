"""
Text extraction / OCR - stage 4 of the pipeline.

Produces one string for the whole document with an explicit page-break
marker between pages. The marker is kept internally (never shown to the
admin and never stored in question text) purely so the question parser can
reason about page boundaries: a question may legitimately continue across a
page break, but the parser must be able to tell a page break from a
question break.

OCR is never assumed to have worked. If pytesseract cannot run - most
commonly because the `tesseract` system binary is not installed on the
server - that is a hard failure surfaced to the admin, not a silent empty
result that would look like "this paper has no questions".
"""
import logging
from dataclasses import dataclass

# PyMuPDF 1.28 deprecated the legacy top-level `fitz` alias in favour of
# `pymupdf`; aliasing keeps the familiar name without the deprecation warning.
import pymupdf as fitz

from app.core.enums import PdfTypeEnum

logger = logging.getLogger(__name__)

# Unlikely to occur in a real question paper, and stripped before anything
# is stored.
PAGE_BREAK_MARKER = "\n<<<LEARNIN_PAGE_BREAK>>>\n"

# Rendering DPI for OCR. 200-300 is the usual sweet spot: below ~150
# tesseract's accuracy falls off badly, above ~300 the memory cost grows
# with no real accuracy gain for printed text.
OCR_RENDER_DPI = 250

OCR_UNAVAILABLE_MESSAGE = (
    "OCR is required for this scanned PDF but the OCR engine isn't available "
    "on this server. Contact an administrator."
)


class OcrUnavailableError(Exception):
    """
    The OCR engine could not be used at all. Message is admin-facing.
    Raised instead of returning empty text, so a missing tesseract can never
    masquerade as "the paper had no questions".
    """


class ExtractionError(Exception):
    """Extraction failed for a reason the admin can be told about."""


def strip_page_markers(text: str) -> str:
    return text.replace(PAGE_BREAK_MARKER, "\n")


def extract_text_layer(content: bytes) -> str:
    """Direct extraction for PDFs that already carry a text layer."""
    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception:
        logger.exception("Text extraction could not open the document")
        raise ExtractionError(
            "The PDF could not be read for text extraction. It may be damaged."
        )

    try:
        pages = []
        for page in document:
            try:
                pages.append(page.get_text())
            except Exception:
                logger.exception("Failed to extract text from a page")
                pages.append("")

        return PAGE_BREAK_MARKER.join(pages)

    finally:
        document.close()


def extract_with_ocr(content: bytes, dpi: int = OCR_RENDER_DPI) -> str:
    """
    Renders each page to an image and OCRs it.

    Raises OcrUnavailableError if the OCR engine cannot be used - callers
    must treat that as a hard failure.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        logger.exception("pytesseract/Pillow are not importable")
        raise OcrUnavailableError(OCR_UNAVAILABLE_MESSAGE)

    import io

    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception:
        logger.exception("OCR could not open the document")
        raise ExtractionError(
            "The PDF could not be read for OCR. It may be damaged."
        )

    try:
        pages = []

        for page_index, page in enumerate(document):
            try:
                pixmap = page.get_pixmap(dpi=dpi)
                image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            except Exception:
                logger.exception("Failed to render page %s for OCR", page_index)
                raise ExtractionError(
                    "This scanned PDF could not be converted to images for OCR. "
                    "Try re-downloading it from the source."
                )

            try:
                pages.append(pytesseract.image_to_string(image))
            except pytesseract.TesseractNotFoundError:
                logger.exception("The tesseract binary is not installed/on PATH")
                raise OcrUnavailableError(OCR_UNAVAILABLE_MESSAGE)
            except Exception:
                # Any other OCR failure is still a failure. We do not fall
                # back to "no text" and pretend the page was blank.
                logger.exception("OCR failed on page %s", page_index)
                raise OcrUnavailableError(
                    "OCR failed while reading this scanned PDF. The page could "
                    "not be converted to text. Contact an administrator."
                )

        return PAGE_BREAK_MARKER.join(pages)

    finally:
        document.close()


def extract_text(content: bytes, pdf_type: PdfTypeEnum) -> tuple[str, bool]:
    """
    Returns (text, ocr_used).

    UNKNOWN is treated as SCANNED: if we could not establish a text layer,
    attempting OCR is the honest option, and a missing OCR engine then
    surfaces as an explicit failure rather than silence.
    """
    if pdf_type == PdfTypeEnum.TEXT:
        return extract_text_layer(content), False

    return extract_with_ocr(content), True


# ------------------------------------------------------- position-aware --
#
# The functions above return one flat string, which is all the question
# parser needs. Associating a diagram with the right question needs more:
# *where on the page* each piece of text came from. These functions return
# the same kind of flat string (so `parse_questions` works unchanged) plus a
# parallel list of `PositionedBlock`s whose `start`/`end` are character
# offsets into that exact string - i.e. slicing the string at a parsed
# question's [start, end) and finding which blocks overlap that range tells
# you which pages/regions that question's text actually came from.

@dataclass
class PositionedBlock:
    page_number: int                 # 0-indexed, matching PyMuPDF/fitz.
    bbox: tuple[float, float, float, float]   # (x0, y0, x1, y1) in PDF points.
    start: int                       # offset into the returned flat text.
    end: int


def extract_text_layer_with_positions(content: bytes) -> tuple[str, list[PositionedBlock]]:
    """Like `extract_text_layer`, but also returns where each chunk of text
    sits on the page - one PositionedBlock per PyMuPDF text block (roughly a
    paragraph/line-group)."""
    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception:
        logger.exception("Text extraction could not open the document")
        raise ExtractionError(
            "The PDF could not be read for text extraction. It may be damaged."
        )

    try:
        pieces: list[str] = []
        blocks: list[PositionedBlock] = []
        cursor = 0

        for page_index, page in enumerate(document):
            try:
                raw_blocks = page.get_text("dict").get("blocks", [])
            except Exception:
                logger.exception("Failed to extract positioned text from a page")
                raw_blocks = []

            for raw_block in raw_blocks:
                if raw_block.get("type") != 0:
                    continue  # not a text block (e.g. an embedded image).

                lines = []
                for line in raw_block.get("lines", []):
                    line_text = "".join(span.get("text", "") for span in line.get("spans", []))
                    if line_text:
                        lines.append(line_text)

                block_text = "\n".join(lines)
                if not block_text.strip():
                    continue

                piece = block_text + "\n"
                blocks.append(PositionedBlock(
                    page_number=page_index,
                    bbox=tuple(raw_block.get("bbox", (0.0, 0.0, 0.0, 0.0))),
                    start=cursor,
                    end=cursor + len(block_text),
                ))
                pieces.append(piece)
                cursor += len(piece)

            pieces.append(PAGE_BREAK_MARKER)
            cursor += len(PAGE_BREAK_MARKER)

        return "".join(pieces), blocks

    finally:
        document.close()


def extract_with_ocr_with_positions(
    content: bytes, dpi: int = OCR_RENDER_DPI
) -> tuple[str, list[PositionedBlock]]:
    """Like `extract_with_ocr`, but also returns each OCR'd line's bounding
    box, converted from the rendered pixel image back to PDF-point space."""
    try:
        import pytesseract
        from pytesseract import Output
        from PIL import Image
    except ImportError:
        logger.exception("pytesseract/Pillow are not importable")
        raise OcrUnavailableError(OCR_UNAVAILABLE_MESSAGE)

    import io

    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception:
        logger.exception("OCR could not open the document")
        raise ExtractionError(
            "The PDF could not be read for OCR. It may be damaged."
        )

    # Pixels-per-PDF-point at this render DPI (a PDF point is always 1/72in),
    # used to map tesseract's pixel-space word boxes back to PDF coordinates.
    scale = dpi / 72.0

    try:
        pieces: list[str] = []
        blocks: list[PositionedBlock] = []
        cursor = 0

        for page_index, page in enumerate(document):
            try:
                pixmap = page.get_pixmap(dpi=dpi)
                image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            except Exception:
                logger.exception("Failed to render page %s for OCR", page_index)
                raise ExtractionError(
                    "This scanned PDF could not be converted to images for OCR. "
                    "Try re-downloading it from the source."
                )

            try:
                data = pytesseract.image_to_data(image, output_type=Output.DICT)
            except pytesseract.TesseractNotFoundError:
                logger.exception("The tesseract binary is not installed/on PATH")
                raise OcrUnavailableError(OCR_UNAVAILABLE_MESSAGE)
            except Exception:
                logger.exception("OCR failed on page %s", page_index)
                raise OcrUnavailableError(
                    "OCR failed while reading this scanned PDF. The page could "
                    "not be converted to text. Contact an administrator."
                )

            # Group words into lines (tesseract's own block/par/line keys),
            # in reading order, then treat each line as one PositionedBlock.
            lines: dict[tuple[int, int, int], dict] = {}
            n_boxes = len(data.get("text", []))
            for i in range(n_boxes):
                word = (data["text"][i] or "").strip()
                if not word:
                    continue

                key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
                left, top = data["left"][i], data["top"][i]
                width, height = data["width"][i], data["height"][i]

                line = lines.setdefault(key, {
                    "words": [], "x0": left, "y0": top, "x1": left + width, "y1": top + height,
                })
                line["words"].append(word)
                line["x0"] = min(line["x0"], left)
                line["y0"] = min(line["y0"], top)
                line["x1"] = max(line["x1"], left + width)
                line["y1"] = max(line["y1"], top + height)

            page_text_parts = []
            for line in lines.values():
                line_text = " ".join(line["words"])
                page_text_parts.append(line_text)

                piece = line_text + "\n"
                blocks.append(PositionedBlock(
                    page_number=page_index,
                    bbox=(
                        line["x0"] / scale, line["y0"] / scale,
                        line["x1"] / scale, line["y1"] / scale,
                    ),
                    start=cursor,
                    end=cursor + len(line_text),
                ))
                cursor += len(piece)
                pieces.append(piece)

            pieces.append(PAGE_BREAK_MARKER)
            cursor += len(PAGE_BREAK_MARKER)

        return "".join(pieces), blocks

    finally:
        document.close()


def extract_text_with_positions(
    content: bytes, pdf_type: PdfTypeEnum
) -> tuple[str, bool, list[PositionedBlock]]:
    """Returns (text, ocr_used, blocks) - the position-aware counterpart to
    `extract_text`, used by the pipeline so it can also detect/associate
    question images. The plain `text`/`ocr_used` are identical in meaning to
    `extract_text`'s, so parsing/storage code is unaffected."""
    if pdf_type == PdfTypeEnum.TEXT:
        text, blocks = extract_text_layer_with_positions(content)
        return text, False, blocks

    text, blocks = extract_with_ocr_with_positions(content)
    return text, True, blocks
