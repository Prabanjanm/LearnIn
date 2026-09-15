"""
Conservative watermark removal - stage 2 of the pipeline.

Design rule: **when in doubt, do nothing and say so.** Silently deleting a
line of a real question is far worse than leaving a watermark in, so a span
is only redacted when it clears an explicit, narrow bar. Anything that
merely *looks* suspicious flags the job as NEEDS_MANUAL_REVIEW and leaves
the PDF untouched - a flag, not a dead end; the admin can still proceed.

This operates purely on *text spans*. Images, tables and diagrams are not
text spans, so this approach cannot touch them - and must not try to. A
picture-based watermark stamped into a scanned page is out of scope and
should be handled by a human, which is exactly what NEEDS_MANUAL_REVIEW is
for.
"""
import logging
import math
import re
from dataclasses import dataclass

# PyMuPDF 1.28 deprecated the legacy top-level `fitz` alias in favour of
# `pymupdf`; aliasing keeps the familiar name without the deprecation warning.
import pymupdf as fitz

from app.core.enums import WatermarkStatusEnum

logger = logging.getLogger(__name__)


# Operators extend this list with literal watermark strings they actually
# encounter (site names, "downloaded from ..." banners). It is intentionally
# an explicit deny-list of *known* sources: nothing is ever added to it
# automatically, and no arbitrary repeated text is treated as safe to remove
# just because it repeats.
KNOWN_WATERMARK_PATTERNS: list[str] = [
    r"(?i)\bdownloaded\s+from\b.*",
    r"(?i)\bwww\.[a-z0-9-]+\.(?:com|in|org|net)\b",
]

_COMPILED_PATTERNS = [re.compile(pattern) for pattern in KNOWN_WATERMARK_PATTERNS]

# A repeated string must appear on at least this share of pages before it is
# even considered a candidate (headers/footers of a real paper repeat too,
# which is why repetition alone is never sufficient).
REPETITION_THRESHOLD = 0.6

# Relative luminance above which text counts as "very light" - typical
# watermark grey/pastel washes sit well above this, real body text is 0.
LIGHT_TEXT_LUMINANCE = 0.72

MIN_CANDIDATE_LENGTH = 4


@dataclass
class WatermarkResult:
    status: WatermarkStatusEnum
    content: bytes | None          # cleaned bytes, or None if untouched
    removed_texts: list[str]
    flagged_texts: list[str]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _luminance(color_int: int) -> float:
    red = ((color_int >> 16) & 0xFF) / 255
    green = ((color_int >> 8) & 0xFF) / 255
    blue = (color_int & 0xFF) / 255
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _is_rotated(span: dict) -> bool:
    """
    PyMuPDF gives each span a writing direction unit vector. Horizontal text
    is (1, 0); anything meaningfully off that axis is rotated - the classic
    diagonal watermark.
    """
    direction = span.get("dir") or (1.0, 0.0)
    try:
        dx, dy = float(direction[0]), float(direction[1])
    except (TypeError, ValueError, IndexError):
        return False

    return not math.isclose(dy, 0.0, abs_tol=0.01) or dx < 0


def _matches_deny_list(text: str) -> bool:
    return any(pattern.search(text) for pattern in _COMPILED_PATTERNS)


def _iter_spans(document):
    """Yields (page_index, page, span_dict) for every text span."""
    for page_index, page in enumerate(document):
        try:
            page_dict = page.get_text("dict")
        except Exception:
            logger.exception("Could not read spans on page %s", page_index)
            continue

        for block in page_dict.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span = dict(span)
                    span.setdefault("dir", line.get("dir", (1.0, 0.0)))
                    yield page_index, page, span


def clean_watermarks(content: bytes) -> WatermarkResult:
    """
    Returns a WatermarkResult. `content` is None unless something was
    actually redacted, in which case it holds the cleaned PDF bytes.
    """
    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception:
        logger.exception("Watermark pass could not open the PDF")
        # Validation already passed, so this is unexpected - but the honest
        # answer is "a human should look", not "assume it was clean".
        return WatermarkResult(
            status=WatermarkStatusEnum.NEEDS_MANUAL_REVIEW,
            content=None,
            removed_texts=[],
            flagged_texts=[],
        )

    try:
        page_count = document.page_count

        # Pass 1: how often does each distinct string appear, and on how
        # many distinct pages?
        pages_by_text: dict[str, set[int]] = {}
        spans_by_text: dict[str, list[tuple[int, dict]]] = {}

        for page_index, _page, span in _iter_spans(document):
            text = _normalize(span.get("text", ""))
            if len(text) < MIN_CANDIDATE_LENGTH:
                continue

            pages_by_text.setdefault(text, set()).add(page_index)
            spans_by_text.setdefault(text, []).append((page_index, span))

        required_pages = max(2, math.ceil(page_count * REPETITION_THRESHOLD))

        remove_texts: set[str] = set()
        flag_texts: set[str] = set()

        for text, pages in pages_by_text.items():
            on_deny_list = _matches_deny_list(text)
            repeats = page_count >= 2 and len(pages) >= required_pages

            if not (on_deny_list or repeats):
                continue

            spans = spans_by_text[text]
            rotated = any(_is_rotated(span) for _page, span in spans)
            light = all(
                _luminance(int(span.get("color", 0))) >= LIGHT_TEXT_LUMINANCE
                for _page, span in spans
            )

            if on_deny_list or rotated or light:
                # Confident: a known bad string, or drawn the way watermarks
                # are drawn rather than the way content is.
                remove_texts.add(text)
            else:
                # Repeats, but reads like an ordinary running header/footer.
                # Refuse to guess.
                flag_texts.add(text)

        if not remove_texts and not flag_texts:
            return WatermarkResult(
                status=WatermarkStatusEnum.NOT_NEEDED,
                content=None,
                removed_texts=[],
                flagged_texts=[],
            )

        if not remove_texts:
            return WatermarkResult(
                status=WatermarkStatusEnum.NEEDS_MANUAL_REVIEW,
                content=None,
                removed_texts=[],
                flagged_texts=sorted(flag_texts),
            )

        # Pass 2: redact only the exact bounding boxes of the confident
        # spans. Never a whole page, never a guessed region.
        pages_touched: set[int] = set()

        for text in remove_texts:
            for page_index, span in spans_by_text[text]:
                page = document[page_index]
                bbox = fitz.Rect(span["bbox"])
                page.add_redact_annot(bbox)
                pages_touched.add(page_index)

        for page_index in pages_touched:
            # images=0 / graphics=0: only the text we targeted is removed;
            # diagrams and figures under the box are left alone.
            document[page_index].apply_redactions(
                images=fitz.PDF_REDACT_IMAGE_NONE
            )

        cleaned = document.tobytes()

        status = (
            WatermarkStatusEnum.NEEDS_MANUAL_REVIEW
            if flag_texts
            else WatermarkStatusEnum.CLEANED
        )

        return WatermarkResult(
            status=status,
            content=cleaned,
            removed_texts=sorted(remove_texts),
            flagged_texts=sorted(flag_texts),
        )

    finally:
        document.close()
