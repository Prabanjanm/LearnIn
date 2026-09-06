"""
Visual content detection - associates diagrams/graphs/tables/figures with
the question they belong to.

A question paper is not pure text. This module never tries to describe,
recreate or OCR a diagram's *meaning* - it only ever preserves the original
pixels, found one of two concrete ways, plus a geometric fallback for
"something is clearly here but wasn't recognised as text or a drawing":

  1. EMBEDDED_RASTER - a real JPEG/PNG image object placed on the page.
     Extracted as-is via `Document.extract_image` (the original encoded
     bytes, not a re-render).
  2. VECTOR_RENDER - PDF vector graphics (paths/curves/fills) rather than an
     embedded image. There is no "extract the vector" operation that
     preserves it faithfully outside a PDF viewer, so the region is rendered
     to a raster crop at high resolution instead - the closest thing to
     "extracting" it without redrawing it.
  3. REGION_RENDER - no embedded image or vector cluster was found, but the
     question's own recognised text leaves an unusually large vertical gap
     unaccounted for on the page. Rather than silently dropping whatever is
     there (a diagram OCR/text-extraction could not read, a badly scanned
     figure, ...), that gap is rendered and preserved, always flagged for
     admin confirmation since a geometric gap is a weaker signal than an
     actual image or drawing object.

Association is purely geometric: a question's `start`/`end` character
offsets (from `question_parser.ParsedQuestion`) are mapped back to the pages
and bounding boxes of the text that produced them (via the same
`PositionedBlock` list the position-aware extractor returned), and every
visual candidate on those pages is assigned to whichever question's vertical
region it falls inside - a region carved so it can never bleed past the
midpoint to a neighbouring question, which is the same "never merge Q10 into
Q11" guarantee `question_parser` gives for text, applied to geometry.

This is a heuristic, same as text/option detection - documented as such, and
the loosest signal (REGION_RENDER) always forces admin review of that
question rather than presenting a guess as settled fact.
"""
import logging
import statistics
from dataclasses import dataclass

import pymupdf as fitz

from app.core.enums import ImageSourceType

from .extraction import PositionedBlock
from .question_parser import ParsedQuestion

logger = logging.getLogger(__name__)

# A vector-drawing cluster smaller than this (in PDF points, ~1/72in) in
# either dimension is treated as decoration (an underline, a table rule, a
# box around an option) rather than a diagram worth preserving as an asset.
MIN_VECTOR_CLUSTER_SIZE = 30.0

# Rects within this many points of each other are merged into one cluster -
# a diagram is very often drawn as many separate path objects (axes, bars,
# labels' boxes) that only make sense as one figure.
VECTOR_MERGE_TOLERANCE = 6.0

# An embedded image or vector cluster covering more than this share of the
# page is almost always the page background or (for a scanned page) the
# single whole-page scan itself, not a sub-figure belonging to one question.
WHOLE_PAGE_AREA_RATIO = 0.75

# A vertical gap between two of a question's own text blocks/lines has to
# exceed max(MIN_GAP_POINTS, GAP_LINE_MULTIPLIER * that page's median line
# height) before it is treated as "something else is here", to avoid
# flagging ordinary paragraph/option spacing.
MIN_GAP_POINTS = 40.0
GAP_LINE_MULTIPLIER = 2.2

RENDER_DPI = 300
CROP_MARGIN = 4.0


@dataclass
class VisualCandidate:
    source_type: ImageSourceType
    page_number: int
    bbox: tuple[float, float, float, float]
    image_bytes: bytes
    ext: str


def _rect_area(rect: fitz.Rect) -> float:
    return max(rect.width, 0) * max(rect.height, 0)


def _expand(rect: fitz.Rect, margin: float, page_rect: fitz.Rect) -> fitz.Rect:
    expanded = fitz.Rect(
        rect.x0 - margin, rect.y0 - margin, rect.x1 + margin, rect.y1 + margin
    )
    return expanded & page_rect


def _question_page_ranges(
    parsed_questions: list[ParsedQuestion],
    blocks: list[PositionedBlock],
) -> dict[int, dict[int, list[PositionedBlock]]]:
    """qi -> page_number -> the question's own blocks on that page, sorted
    top-to-bottom. A block "belongs" to a question if its character range
    overlaps the question's [start, end)."""
    result: dict[int, dict[int, list[PositionedBlock]]] = {}

    for qi, question in enumerate(parsed_questions):
        by_page: dict[int, list[PositionedBlock]] = {}
        for block in blocks:
            if block.start < question.end and block.end > question.start:
                by_page.setdefault(block.page_number, []).append(block)

        for page_blocks in by_page.values():
            page_blocks.sort(key=lambda b: b.bbox[1])

        result[qi] = by_page

    return result


def _page_boundaries(
    question_ranges: dict[int, dict[int, list[PositionedBlock]]],
    page_heights: dict[int, float],
) -> dict[int, list[tuple[int, float, float, bool]]]:
    """page_number -> [(qi, top, bottom, bottom_is_closed), ...] sorted by
    top, where each question's [top, bottom) is expanded halfway to its
    neighbours on that page (or to the page edge) - a search rectangle a
    visual can never escape into the wrong question. `bottom_is_closed` is
    True only when `bottom` is a real midpoint with a following question on
    this same page, not simply "the page ends here" - the trailing-gap
    fallback in `detect_question_visuals` must not mistake an entirely
    ordinary end-of-page for a missing diagram."""
    per_page: dict[int, list[tuple[int, float, float]]] = {}

    for qi, by_page in question_ranges.items():
        for page_number, page_blocks in by_page.items():
            y0 = min(b.bbox[1] for b in page_blocks)
            y1 = max(b.bbox[3] for b in page_blocks)
            per_page.setdefault(page_number, []).append((qi, y0, y1))

    boundaries: dict[int, list[tuple[int, float, float, bool]]] = {}
    for page_number, entries in per_page.items():
        entries.sort(key=lambda item: item[1])
        page_height = page_heights.get(page_number, entries[-1][2])

        expanded: list[tuple[int, float, float, bool]] = []
        for index, (qi, y0, y1) in enumerate(entries):
            top = 0.0 if index == 0 else (entries[index - 1][2] + y0) / 2
            is_last_on_page = index == len(entries) - 1
            bottom = (
                page_height if is_last_on_page
                else (y1 + entries[index + 1][1]) / 2
            )
            expanded.append((qi, top, bottom, not is_last_on_page))

        boundaries[page_number] = expanded

    return boundaries


def _question_at(boundaries: list[tuple[int, float, float, bool]], y_center: float) -> int | None:
    for qi, top, bottom, _closed in boundaries:
        if top <= y_center < bottom:
            return qi
    return None


def _cluster_rects(rects: list[fitz.Rect], tolerance: float) -> list[fitz.Rect]:
    """Union-find style merge of overlapping/near rects into bounding boxes -
    a diagram is usually many separate vector path objects, not one."""
    if not rects:
        return []

    padded = [fitz.Rect(r.x0 - tolerance, r.y0 - tolerance, r.x1 + tolerance, r.y1 + tolerance) for r in rects]
    parent = list(range(len(rects)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            if padded[i].intersects(padded[j]):
                union(i, j)

    groups: dict[int, fitz.Rect] = {}
    for i, rect in enumerate(rects):
        root = find(i)
        if root not in groups:
            groups[root] = fitz.Rect(rect)
        else:
            groups[root] |= rect

    return list(groups.values())


def detect_question_visuals(
    content: bytes,
    parsed_questions: list[ParsedQuestion],
    blocks: list[PositionedBlock],
) -> dict[int, list[VisualCandidate]]:
    """
    Returns {parsed_question_index: [VisualCandidate, ...]}, ordered
    page-then-position. Never raises for a detection failure on one page or
    one object - a single bad image/drawing is logged and skipped rather
    than losing every diagram in the document.
    """
    if not parsed_questions:
        return {}

    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception:
        logger.exception("Visual detection could not open the document")
        return {}

    try:
        question_ranges = _question_page_ranges(parsed_questions, blocks)
        page_heights = {page.number: page.rect.height for page in document}
        boundaries = _page_boundaries(question_ranges, page_heights)

        results: dict[int, list[VisualCandidate]] = {qi: [] for qi in range(len(parsed_questions))}
        # Tracks claimed vertical spans per (qi, page) so the REGION_RENDER
        # gap pass does not re-render territory an image/vector already covers.
        claimed: dict[tuple[int, int], list[tuple[float, float]]] = {}

        for page_number, page_boundaries in boundaries.items():
            page = document[page_number]
            page_rect = page.rect

            # ---------------------------------------------- embedded raster --
            try:
                images = page.get_images(full=True)
            except Exception:
                logger.exception("Could not list embedded images on page %s", page_number)
                images = []

            seen_xrefs: set[int] = set()
            for image_info in images:
                xref = image_info[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)

                try:
                    rects = page.get_image_rects(xref)
                except Exception:
                    continue

                for rect in rects:
                    if _rect_area(rect) <= 0:
                        continue
                    if _rect_area(rect) / max(_rect_area(page_rect), 1) >= WHOLE_PAGE_AREA_RATIO:
                        # The whole scanned page (or a full-page background),
                        # not a sub-figure belonging to one question.
                        continue

                    y_center = (rect.y0 + rect.y1) / 2
                    qi = _question_at(page_boundaries, y_center)
                    if qi is None:
                        continue

                    try:
                        extracted = document.extract_image(xref)
                    except Exception:
                        logger.exception("Could not extract embedded image xref=%s", xref)
                        continue

                    results[qi].append(VisualCandidate(
                        source_type=ImageSourceType.EMBEDDED_RASTER,
                        page_number=page_number,
                        bbox=(rect.x0, rect.y0, rect.x1, rect.y1),
                        image_bytes=extracted["image"],
                        ext=extracted.get("ext", "png"),
                    ))
                    claimed.setdefault((qi, page_number), []).append((rect.y0, rect.y1))

            # ------------------------------------------------ vector drawings --
            try:
                drawings = page.get_drawings()
            except Exception:
                logger.exception("Could not read vector drawings on page %s", page_number)
                drawings = []

            raw_rects = [d["rect"] for d in drawings if d.get("rect") and _rect_area(d["rect"]) > 0]
            for cluster in _cluster_rects(raw_rects, VECTOR_MERGE_TOLERANCE):
                if cluster.width < MIN_VECTOR_CLUSTER_SIZE or cluster.height < MIN_VECTOR_CLUSTER_SIZE:
                    continue
                if _rect_area(cluster) / max(_rect_area(page_rect), 1) >= WHOLE_PAGE_AREA_RATIO:
                    continue

                y_center = (cluster.y0 + cluster.y1) / 2
                qi = _question_at(page_boundaries, y_center)
                if qi is None:
                    continue

                crop = _expand(cluster, CROP_MARGIN, page_rect)
                try:
                    pixmap = page.get_pixmap(clip=crop, dpi=RENDER_DPI)
                    image_bytes = pixmap.tobytes("png")
                except Exception:
                    logger.exception("Could not render vector region on page %s", page_number)
                    continue

                results[qi].append(VisualCandidate(
                    source_type=ImageSourceType.VECTOR_RENDER,
                    page_number=page_number,
                    bbox=(crop.x0, crop.y0, crop.x1, crop.y1),
                    image_bytes=image_bytes,
                    ext="png",
                ))
                claimed.setdefault((qi, page_number), []).append((cluster.y0, cluster.y1))

            # ------------------------------------- region-render fallback gaps --
            line_heights = [b.bbox[3] - b.bbox[1] for b in blocks if b.page_number == page_number]
            median_height = statistics.median(line_heights) if line_heights else 20.0
            gap_threshold = max(MIN_GAP_POINTS, GAP_LINE_MULTIPLIER * median_height)

            for qi, top, bottom, bottom_is_closed in page_boundaries:
                own_blocks = question_ranges.get(qi, {}).get(page_number, [])
                if not own_blocks:
                    continue

                claimed_spans = claimed.get((qi, page_number), [])

                def _already_claimed(gap_top: float, gap_bottom: float) -> bool:
                    for span_top, span_bottom in claimed_spans:
                        overlap = min(gap_bottom, span_bottom) - max(gap_top, span_top)
                        if overlap > 0 and overlap >= 0.5 * (gap_bottom - gap_top):
                            return True
                    return False

                gaps: list[tuple[float, float]] = []
                for prev_block, next_block in zip(own_blocks, own_blocks[1:]):
                    gap_top = prev_block.bbox[3]
                    gap_bottom = next_block.bbox[1]
                    if gap_bottom - gap_top >= gap_threshold:
                        gaps.append((gap_top, gap_bottom))

                # Only checked when this question actually continues into
                # another question on the same page - an ordinary end of
                # page/paper is not evidence of a missing diagram.
                if bottom_is_closed:
                    trailing_top = own_blocks[-1].bbox[3]
                    if bottom - trailing_top >= gap_threshold:
                        gaps.append((trailing_top, bottom))

                for gap_top, gap_bottom in gaps:
                    if _already_claimed(gap_top, gap_bottom):
                        continue

                    rect = fitz.Rect(0, gap_top, page_rect.width, gap_bottom)
                    crop = _expand(rect, CROP_MARGIN, page_rect)

                    try:
                        pixmap = page.get_pixmap(clip=crop, dpi=RENDER_DPI)
                        image_bytes = pixmap.tobytes("png")
                    except Exception:
                        logger.exception("Could not render fallback region on page %s", page_number)
                        continue

                    results[qi].append(VisualCandidate(
                        source_type=ImageSourceType.REGION_RENDER,
                        page_number=page_number,
                        bbox=(crop.x0, crop.y0, crop.x1, crop.y1),
                        image_bytes=image_bytes,
                        ext="png",
                    ))

        return {qi: candidates for qi, candidates in results.items() if candidates}

    finally:
        document.close()
