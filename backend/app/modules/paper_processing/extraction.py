"""
Text extraction / OCR - stage 4 of the pipeline.

Produces one string for the whole document with an explicit page-break
marker between pages. The marker is kept internally (never shown to the
admin and never stored in question text) purely so the question parser can
reason about page boundaries: a question may legitimately continue across a
page break, but the parser must be able to tell a page break from a
question break.

OCR is never assumed to have worked. If the configured engine cannot run -
Gemini with no/invalid GEMINI_API_KEY, or pytesseract with the `tesseract`
system binary missing - that is a hard failure surfaced to the admin, not a
silent empty result that would look like "this paper has no questions".

Two OCR engines are supported:
  - Gemini (preferred whenever settings.GEMINI_API_KEY is set) - a page
    image in, one whole block of transcribed text per page out. Faster and
    generally more accurate than Tesseract on real exam-paper scans, at the
    cost of page-level (not line-level) position data - see
    extract_with_gemini_with_positions.
  - Tesseract/pytesseract (the fallback when no Gemini key is configured) -
    line-level position data via image_to_data, used by the diagram/image
    association pass (question_visuals.py) to associate a diagram with the
    exact question it belongs to, even when several questions share a page.
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

# PyMuPDF 1.28 deprecated the legacy top-level `fitz` alias in favour of
# `pymupdf`; aliasing keeps the familiar name without the deprecation warning.
import pymupdf as fitz

from app.common.exceptions.exceptions import GeminiConfigError
from app.core.config import settings
from app.core.enums import PdfTypeEnum
from app.core.gemini_client import get_gemini_client

logger = logging.getLogger(__name__)

# Unlikely to occur in a real question paper, and stripped before anything
# is stored.
PAGE_BREAK_MARKER = "\n<<<LEARNIN_PAGE_BREAK>>>\n"

# Rendering DPI for OCR. 200-300 is the usual sweet spot: below ~150
# tesseract's accuracy falls off badly, above ~300 the memory cost grows
# with no real accuracy gain for printed text.
OCR_RENDER_DPI = 250

# `pytesseract` shells out to the system `tesseract` binary as a separate OS
# process per call, so it does not hold Python's GIL while it runs - running
# several pages' OCR calls concurrently from a small thread pool gives a real
# wall-clock win on multi-page scanned papers. Page *rendering* (PyMuPDF) is
# NOT parallelized this way: rendering pages of the same fitz.Document from
# multiple threads is not safe, so every page is rendered to a plain PIL
# image on the main thread first, and only the (much slower) OCR calls on
# those already-rendered images are handed to the pool.
OCR_MAX_WORKERS = 4

# Lower than OCR_RENDER_DPI: a vision model's encoder tiles/downsamples the
# image internally, so more DPI does not add fidelity here, only a bigger,
# slower upload - 200 is plenty legible for a page of printed exam text.
GEMINI_RENDER_DPI = 200

OCR_UNAVAILABLE_MESSAGE = (
    "OCR is required for this scanned PDF but the OCR engine isn't available "
    "on this server. Contact an administrator."
)

GEMINI_UNAVAILABLE_MESSAGE = (
    "OCR is required for this scanned PDF but Gemini isn't available right "
    "now. Try again shortly, or contact an administrator."
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
        images = []
        for page_index, page in enumerate(document):
            try:
                pixmap = page.get_pixmap(dpi=dpi)
                images.append(Image.open(io.BytesIO(pixmap.tobytes("png"))))
            except Exception:
                logger.exception("Failed to render page %s for OCR", page_index)
                raise ExtractionError(
                    "This scanned PDF could not be converted to images for OCR. "
                    "Try re-downloading it from the source."
                )
    finally:
        document.close()

    pages: list[str | None] = [None] * len(images)
    with ThreadPoolExecutor(max_workers=min(OCR_MAX_WORKERS, len(images)) or 1) as executor:
        futures = [executor.submit(pytesseract.image_to_string, image) for image in images]

        for page_index, future in enumerate(futures):
            try:
                pages[page_index] = future.result()
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


def extract_with_gemini(content: bytes, dpi: int = GEMINI_RENDER_DPI) -> str:
    """
    Renders each page to an image and transcribes it with Gemini.

    Raises OcrUnavailableError if Gemini cannot be used - callers must treat
    that as a hard failure, same as extract_with_ocr's pytesseract failures.
    """
    import io

    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception:
        logger.exception("OCR could not open the document")
        raise ExtractionError(
            "The PDF could not be read for OCR. It may be damaged."
        )

    try:
        images = []
        for page_index, page in enumerate(document):
            try:
                pixmap = page.get_pixmap(dpi=dpi)
                images.append(pixmap.tobytes("png"))
            except Exception:
                logger.exception("Failed to render page %s for OCR", page_index)
                raise ExtractionError(
                    "This scanned PDF could not be converted to images for OCR. "
                    "Try re-downloading it from the source."
                )
    finally:
        document.close()

    client = get_gemini_client()

    pages: list[str | None] = [None] * len(images)
    with ThreadPoolExecutor(max_workers=min(OCR_MAX_WORKERS, len(images)) or 1) as executor:
        futures = [executor.submit(client.extract_text_from_image, image) for image in images]

        for page_index, future in enumerate(futures):
            try:
                pages[page_index] = future.result()
            except GeminiConfigError:
                logger.exception("Gemini is not configured")
                raise OcrUnavailableError(GEMINI_UNAVAILABLE_MESSAGE)
            except Exception:
                # Any other failure - network, quota, a malformed response -
                # is still a failure. We do not fall back to "no text" and
                # pretend the page was blank.
                logger.exception("Gemini OCR failed on page %s", page_index)
                raise OcrUnavailableError(GEMINI_UNAVAILABLE_MESSAGE)

    return PAGE_BREAK_MARKER.join(pages)


def extract_text(content: bytes, pdf_type: PdfTypeEnum) -> tuple[str, bool]:
    """
    Returns (text, ocr_used).

    UNKNOWN is treated as SCANNED: if we could not establish a text layer,
    attempting OCR is the honest option, and a missing OCR engine then
    surfaces as an explicit failure rather than silence.

    Gemini is used for OCR whenever settings.GEMINI_API_KEY is configured;
    pytesseract is the fallback only when no key is set at all. There is no
    silent runtime fallback between the two - a configured-but-failing
    Gemini call is a real, surfaced OcrUnavailableError, not a silently
    different engine's result.
    """
    if pdf_type == PdfTypeEnum.TEXT:
        return extract_text_layer(content), False

    if settings.GEMINI_API_KEY:
        return extract_with_gemini(content), True

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
    paragraph/line-group).

    Uses page.get_text("blocks") rather than "dict": both carry the same
    per-block bbox + text this function actually needs, but "dict" also
    builds a full span-level tree (font, size, color, flags for every run of
    text) that is immediately discarded here - "blocks" skips building that
    and is dramatically cheaper (~40x on a typical page in local timing) for
    exactly the same result.
    """
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
                # Each tuple: (x0, y0, x1, y1, text, block_no, block_type).
                # block_type 0 = text, 1 = image - only text blocks matter
                # here, an embedded image is handled separately (see
                # question_visuals.py).
                raw_blocks = page.get_text("blocks")
            except Exception:
                logger.exception("Failed to extract positioned text from a page")
                raw_blocks = []

            for raw_block in raw_blocks:
                x0, y0, x1, y1, raw_text, _block_no, block_type = raw_block[:7]
                if block_type != 0:
                    continue  # not a text block (e.g. an embedded image).

                # PyMuPDF terminates each block's text with a trailing "\n";
                # strip it so `end` below matches the un-terminated length
                # this function has always reported.
                block_text = raw_text.rstrip("\n")
                if not block_text.strip():
                    continue

                piece = block_text + "\n"
                blocks.append(PositionedBlock(
                    page_number=page_index,
                    bbox=(x0, y0, x1, y1),
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
        images = []
        for page_index, page in enumerate(document):
            try:
                pixmap = page.get_pixmap(dpi=dpi)
                images.append(Image.open(io.BytesIO(pixmap.tobytes("png"))))
            except Exception:
                logger.exception("Failed to render page %s for OCR", page_index)
                raise ExtractionError(
                    "This scanned PDF could not be converted to images for OCR. "
                    "Try re-downloading it from the source."
                )
    finally:
        document.close()

    page_data: list[dict | None] = [None] * len(images)
    with ThreadPoolExecutor(max_workers=min(OCR_MAX_WORKERS, len(images)) or 1) as executor:
        futures = [
            executor.submit(pytesseract.image_to_data, image, output_type=Output.DICT)
            for image in images
        ]

        for page_index, future in enumerate(futures):
            try:
                page_data[page_index] = future.result()
            except pytesseract.TesseractNotFoundError:
                logger.exception("The tesseract binary is not installed/on PATH")
                raise OcrUnavailableError(OCR_UNAVAILABLE_MESSAGE)
            except Exception:
                logger.exception("OCR failed on page %s", page_index)
                raise OcrUnavailableError(
                    "OCR failed while reading this scanned PDF. The page could "
                    "not be converted to text. Contact an administrator."
                )

    pieces: list[str] = []
    blocks: list[PositionedBlock] = []
    cursor = 0

    for page_index, data in enumerate(page_data):
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


def extract_with_gemini_with_positions(
    content: bytes, dpi: int = GEMINI_RENDER_DPI
) -> tuple[str, list[PositionedBlock]]:
    """
    Like `extract_with_gemini`, but also returns position data - one
    PositionedBlock per PAGE (not per line), spanning that whole page's
    text and the full page rect as its bbox.

    This is coarser than `extract_with_ocr_with_positions`'s per-line boxes:
    a page with more than one question sharing an embedded image/diagram
    cannot be split precisely between them from page-level position data
    alone (see question_visuals.py's boundary logic), so that association
    degrades to page granularity for Gemini-processed pages. A page with
    only one question is unaffected. This trade-off is deliberate - it
    keeps Gemini OCR fast and simple, at a real but narrow cost.
    """
    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception:
        logger.exception("OCR could not open the document")
        raise ExtractionError(
            "The PDF could not be read for OCR. It may be damaged."
        )

    try:
        images = []
        page_rects: list[fitz.Rect] = []
        for page_index, page in enumerate(document):
            try:
                pixmap = page.get_pixmap(dpi=dpi)
                images.append(pixmap.tobytes("png"))
                page_rects.append(page.rect)
            except Exception:
                logger.exception("Failed to render page %s for OCR", page_index)
                raise ExtractionError(
                    "This scanned PDF could not be converted to images for OCR. "
                    "Try re-downloading it from the source."
                )
    finally:
        document.close()

    client = get_gemini_client()

    page_texts: list[str | None] = [None] * len(images)
    with ThreadPoolExecutor(max_workers=min(OCR_MAX_WORKERS, len(images)) or 1) as executor:
        futures = [executor.submit(client.extract_text_from_image, image) for image in images]

        for page_index, future in enumerate(futures):
            try:
                page_texts[page_index] = future.result()
            except GeminiConfigError:
                logger.exception("Gemini is not configured")
                raise OcrUnavailableError(GEMINI_UNAVAILABLE_MESSAGE)
            except Exception:
                logger.exception("Gemini OCR failed on page %s", page_index)
                raise OcrUnavailableError(GEMINI_UNAVAILABLE_MESSAGE)

    pieces: list[str] = []
    blocks: list[PositionedBlock] = []
    cursor = 0

    for page_index, page_text in enumerate(page_texts):
        page_text = (page_text or "").strip()
        page_rect = page_rects[page_index]

        if page_text:
            piece = page_text + "\n"
            blocks.append(PositionedBlock(
                page_number=page_index,
                bbox=(page_rect.x0, page_rect.y0, page_rect.x1, page_rect.y1),
                start=cursor,
                end=cursor + len(page_text),
            ))
            pieces.append(piece)
            cursor += len(piece)

        pieces.append(PAGE_BREAK_MARKER)
        cursor += len(PAGE_BREAK_MARKER)

    return "".join(pieces), blocks


def extract_text_with_positions(
    content: bytes, pdf_type: PdfTypeEnum
) -> tuple[str, bool, list[PositionedBlock]]:
    """Returns (text, ocr_used, blocks) - the position-aware counterpart to
    `extract_text`, used by the pipeline so it can also detect/associate
    question images. The plain `text`/`ocr_used` are identical in meaning to
    `extract_text`'s, so parsing/storage code is unaffected.

    Gemini vs pytesseract dispatch rule matches `extract_text`'s exactly -
    see its docstring."""
    if pdf_type == PdfTypeEnum.TEXT:
        text, blocks = extract_text_layer_with_positions(content)
        return text, False, blocks

    if settings.GEMINI_API_KEY:
        text, blocks = extract_with_gemini_with_positions(content)
        return text, True, blocks

    text, blocks = extract_with_ocr_with_positions(content)
    return text, True, blocks
