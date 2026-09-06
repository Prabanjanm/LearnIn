"""
Standardized LearnIn PDF generation - stage 7 of the pipeline.

Builds a clean, consistently typeset paper from the *reviewed* content
only. It reads `ExtractedQuestion`/`ExtractedOption` rows, which by this
point an admin has gone through by hand - the generator itself adds no
content of its own beyond headings and labels.

Bytes are returned to the caller for upload to Drive; nothing is written to
local disk.
"""
import html
import io
import logging
import os
from typing import Callable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

LOGO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "static", "images", "logo.png",
)
LOGO_HEIGHT = 12 * mm
HEADER_RULE_Y = 30 * mm
FOOTER_RULE_Y = 18 * mm
PAGE_BORDER_INSET = 6 * mm

MARGIN = 18 * mm
CONTENT_WIDTH = A4[0] - 2 * MARGIN

# A question's diagram/photo is a supporting figure, not the main content -
# capping it well under the content width keeps one image from dominating
# the printed page the way a full-bleed photo would.
MAX_IMAGE_WIDTH = 70 * mm
MAX_IMAGE_HEIGHT = 55 * mm

# Images are only ever displayed at up to CONTENT_WIDTH x MAX_IMAGE_HEIGHT in
# the finished PDF, so there is no point embedding a source photo at its full
# (often multi-megapixel) resolution - that is what was making generated
# PDFs balloon in size. 200dpi is comfortably sharp for print at that
# physical size while keeping the encoded bytes small.
IMAGE_TARGET_DPI = 200
IMAGE_JPEG_QUALITY = 78

BRAND = "LearnIn"
TAGLINE = "Learn Today, Lead Tomorrow"
DOCUMENT_KIND = "Previous Year Question Paper"

BRAND_COLOR = colors.HexColor("#1f4ed8")
NAVY_COLOR = colors.HexColor("#101d4d")

MUTED_COLOR = colors.HexColor("#4b5563")


def _styles() -> dict:
    base = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "LearnInTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            spaceAfter=4,
            textColor=colors.black,
        ),
        "subtitle": ParagraphStyle(
            "LearnInSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            alignment=TA_CENTER,
            textColor=MUTED_COLOR,
        ),
        "meta": ParagraphStyle(
            "LearnInMeta",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=MUTED_COLOR,
        ),
        "question": ParagraphStyle(
            "LearnInQuestion",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=16,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "option": ParagraphStyle(
            "LearnInOption",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            leftIndent=16,
            spaceAfter=1.5,
        ),
        "answer": ParagraphStyle(
            "LearnInAnswer",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9.5,
            leading=14,
            leftIndent=16,
            spaceBefore=3,
            textColor=MUTED_COLOR,
        ),
    }


def _escape(text: str) -> str:
    """
    Platypus parses a mini-HTML dialect, so raw '<' and '&' from an
    extracted question would either break the build or be silently
    reinterpreted as markup. Escaping keeps the printed text identical to
    the reviewed text.
    """
    return html.escape(text or "", quote=False)


_logo_reader: ImageReader | None = None
_logo_load_attempted = False


def _logo() -> ImageReader | None:
    """Lazily loads and caches the brand logo - read once per process, not
    once per page."""
    global _logo_reader, _logo_load_attempted

    if not _logo_load_attempted:
        _logo_load_attempted = True
        try:
            # The source logo asset is a large square PNG (meant for
            # screens/favicons); drawn at LOGO_HEIGHT it only ever needs a
            # few hundred pixels, so downsample once here instead of
            # embedding the multi-hundred-KB original in every generated PDF.
            from PIL import Image as PILImage, ImageChops

            source = PILImage.open(LOGO_PATH).convert("RGBA")
            source.load()

            # The source asset is a square icon sitting on a near-white
            # background with margin around the mark. Left uncropped, that
            # margin becomes part of the drawn box and throws off vertical
            # alignment against the header text baseline next to it - so
            # crop to the mark's actual bounding box and make the
            # background transparent before placing it in the header.
            background = PILImage.new("RGBA", source.size, source.getpixel((0, 0)))
            diff = ImageChops.difference(source.convert("RGB"), background.convert("RGB"))
            bbox = diff.getbbox()
            if bbox:
                source = source.crop(bbox)

            bg_r, bg_g, bg_b, _ = background.getpixel((0, 0))
            pixels = source.load()
            for y in range(source.height):
                for x in range(source.width):
                    r, g, b, a = pixels[x, y]
                    if abs(r - bg_r) <= 6 and abs(g - bg_g) <= 6 and abs(b - bg_b) <= 6:
                        pixels[x, y] = (r, g, b, 0)

            target_px = max(1, round(IMAGE_TARGET_DPI * LOGO_HEIGHT / mm / 25.4))
            width_px = max(1, round(target_px * source.width / source.height))
            source = source.resize((width_px, target_px), PILImage.LANCZOS)

            encoded = io.BytesIO()
            source.save(encoded, format="PNG", optimize=True)
            encoded.seek(0)
            _logo_reader = ImageReader(encoded)
        except Exception:
            logger.exception("Could not load the brand logo for the generated PDF")
            _logo_reader = None

    return _logo_reader


def _draw_envelope_icon(canvas, x: float, y: float, size: float) -> None:
    """A tiny envelope glyph drawn from primitives - core PDF fonts have no
    reliable envelope character, so this draws one instead of risking a
    missing-glyph box in front of the footer email address."""
    width = size * 1.3
    canvas.setStrokeColor(NAVY_COLOR)
    canvas.setLineWidth(0.6)
    canvas.rect(x, y, width, size, stroke=1, fill=0)
    canvas.line(x, y + size, x + width / 2, y + size * 0.4)
    canvas.line(x + width, y + size, x + width / 2, y + size * 0.4)


def _draw_page_furniture(canvas, document, header_text: str, total_pages: int | None = None) -> None:
    """Runs on every page: a thin border frame, the logo/wordmark and
    document-kind label up top, copyright/email/page number at the foot."""
    canvas.saveState()

    width, height = A4

    canvas.setStrokeColor(NAVY_COLOR)
    canvas.setLineWidth(0.8)
    canvas.rect(
        PAGE_BORDER_INSET,
        PAGE_BORDER_INSET,
        width - 2 * PAGE_BORDER_INSET,
        height - 2 * PAGE_BORDER_INSET,
        stroke=1,
        fill=0,
    )

    rule_y = height - HEADER_RULE_Y
    wordmark_baseline = rule_y + 10 * mm
    tagline_baseline = rule_y + 4 * mm

    logo = _logo()
    text_x = 18 * mm
    if logo is not None:
        logo_width = LOGO_HEIGHT * logo.getSize()[0] / logo.getSize()[1]
        canvas.drawImage(
            logo,
            18 * mm,
            tagline_baseline,
            width=logo_width,
            height=LOGO_HEIGHT,
            mask="auto",
        )
        text_x = 18 * mm + logo_width + 4 * mm

    canvas.setFont("Helvetica-Bold", 20)
    canvas.setFillColor(NAVY_COLOR)
    canvas.drawString(text_x, wordmark_baseline, "Learn")
    learn_width = canvas.stringWidth("Learn", "Helvetica-Bold", 20)
    canvas.setFillColor(BRAND_COLOR)
    canvas.drawString(text_x + learn_width, wordmark_baseline, "In")

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED_COLOR)
    canvas.drawString(text_x, tagline_baseline, TAGLINE)

    canvas.setFont("Helvetica-Bold", 12)
    canvas.setFillColor(NAVY_COLOR)
    canvas.drawRightString(width - 18 * mm, wordmark_baseline - 2, DOCUMENT_KIND)

    canvas.setStrokeColor(NAVY_COLOR)
    canvas.setLineWidth(1)
    canvas.line(18 * mm, rule_y, width - 18 * mm, rule_y)

    footer_rule_y = FOOTER_RULE_Y
    canvas.line(18 * mm, footer_rule_y, width - 18 * mm, footer_rule_y)

    page_label = (
        f"Page {canvas.getPageNumber()} of {total_pages}"
        if total_pages
        else f"Page {canvas.getPageNumber()}"
    )

    footer_text_y = footer_rule_y - 6 * mm

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(NAVY_COLOR)
    canvas.drawString(18 * mm, footer_text_y, f"© {BRAND}. All rights reserved.")
    canvas.drawCentredString(width / 2, footer_text_y, page_label)

    email = "learnin.website@gmail.com"
    email_width = canvas.stringWidth(email, "Helvetica", 8)
    icon_size = 3 * mm
    icon_gap = 1.5 * mm
    canvas.drawRightString(width - 18 * mm, footer_text_y, email)
    _draw_envelope_icon(
        canvas,
        width - 18 * mm - email_width - icon_gap - icon_size * 1.3,
        footer_text_y - 0.5 * mm,
        icon_size,
    )

    canvas.restoreState()


class _NumberedCanvas(Canvas):
    """
    Buffers every page so the footer can show "Page X of N" - reportlab
    only knows the final page count once the whole story has been laid
    out, so a single-pass onPage callback cannot print it.
    """

    def __init__(self, *args, on_page=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_pages = []
        self._on_page = on_page

    def showPage(self):
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_pages)
        for state in self._saved_pages:
            self.__dict__.update(state)
            if self._on_page is not None:
                self._on_page(self, total_pages)
            super().showPage()
        super().save()


def _image_flowable(image_bytes: bytes, max_width: float = MAX_IMAGE_WIDTH) -> RLImage | None:
    """
    Scales one preserved diagram/figure to fit within `max_width` (and a
    sane max height, so one tall figure cannot silently eat several
    pages). The image is downsampled to the resolution it will actually be
    printed at and re-encoded as JPEG - the *content* of the diagram is
    unchanged, only the pixel density and file size, which is what keeps
    the generated PDF from ballooning past what a screen-sized photo needs.
    """
    try:
        from PIL import Image as PILImage
        source = PILImage.open(io.BytesIO(image_bytes))
        source.load()
    except Exception:
        logger.exception("Could not read a question image's dimensions for the generated PDF")
        return None

    pixel_width, pixel_height = source.size
    if not pixel_width or not pixel_height:
        return None

    draw_width = max_width
    draw_height = draw_width * pixel_height / pixel_width

    if draw_height > MAX_IMAGE_HEIGHT:
        draw_height = MAX_IMAGE_HEIGHT
        draw_width = draw_height * pixel_width / pixel_height

    target_pixel_width = max(1, round(draw_width / mm / 25.4 * IMAGE_TARGET_DPI))
    target_pixel_height = max(1, round(draw_height / mm / 25.4 * IMAGE_TARGET_DPI))

    try:
        if source.mode in ("RGBA", "LA", "P"):
            flattened = PILImage.new("RGB", source.size, "white")
            rgba = source.convert("RGBA")
            flattened.paste(rgba, mask=rgba.split()[-1])
            source = flattened
        elif source.mode != "RGB":
            source = source.convert("RGB")

        if target_pixel_width < pixel_width or target_pixel_height < pixel_height:
            source = source.resize((target_pixel_width, target_pixel_height), PILImage.LANCZOS)

        encoded = io.BytesIO()
        source.save(encoded, format="JPEG", quality=IMAGE_JPEG_QUALITY, optimize=True)
        encoded.seek(0)
    except Exception:
        logger.exception("Could not re-encode a question image for the generated PDF")
        encoded = io.BytesIO(image_bytes)

    flowable = RLImage(encoded, width=draw_width, height=draw_height)
    flowable.hAlign = "CENTER"
    return flowable


def build_paper_pdf(
    title: str,
    year: int,
    subject_name: str | None,
    department_name: str | None,
    exam_name: str | None,
    questions: list,
    image_loader: Callable[[str], bytes] | None = None,
) -> bytes:
    """
    `questions` is an ordered iterable of ExtractedQuestion-shaped objects
    (question_text, correct_answer, `options` ordered by label, and
    `images` ordered by order_index).

    `image_loader`, if given, is called with a Drive file_id and must return
    the image's raw bytes - this module has no Drive dependency of its own,
    it just draws whatever bytes it is handed. A question's diagrams are
    embedded exactly as stored (no redrawing/recreation); a diagram that
    fails to load or decode is skipped for that one question rather than
    failing the whole document.

    Returns the PDF bytes.
    """
    styles = _styles()
    buffer = io.BytesIO()

    header_text = " / ".join(
        part for part in (exam_name, department_name, subject_name) if part
    ) or BRAND

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=HEADER_RULE_Y + 6 * mm,
        bottomMargin=FOOTER_RULE_Y + 10 * mm,
        title=title,
        author=BRAND,
        subject=f"{subject_name or ''} {year}".strip(),
    )

    story = []

    story.append(Paragraph(_escape(title), styles["title"]))

    meta_line = "  |  ".join(
        part for part in (
            exam_name,
            department_name,
            subject_name,
            str(year),
        ) if part
    )
    story.append(Paragraph(_escape(meta_line), styles["subtitle"]))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#e5e7eb")))
    story.append(Spacer(1, 4))

    if not questions:
        story.append(Paragraph(
            "No questions were included in this paper.",
            styles["meta"],
        ))

    for position, question in enumerate(questions, start=1):
        flowables = [
            Paragraph(
                f"{position}. {_escape(question.question_text)}",
                styles["question"],
            )
        ]

        if image_loader is not None:
            images = getattr(question, "images", [])
            image_bytes_list = []
            for image in images:
                try:
                    image_bytes_list.append(image_loader(image.file_id))
                except Exception:
                    logger.exception(
                        "Could not load question image %s for the generated PDF", image.file_id
                    )

            # Several images for one question have plenty of page width to
            # share, so lay them out side by side in a row instead of
            # stacking each one on its own line - each gets an equal slice
            # of the content width (minus the gaps between them).
            gap = 4 * mm
            per_image_width = min(
                MAX_IMAGE_WIDTH,
                (CONTENT_WIDTH - gap * (len(image_bytes_list) - 1)) / len(image_bytes_list),
            ) if image_bytes_list else MAX_IMAGE_WIDTH

            image_flowables = [
                flowable
                for image_bytes in image_bytes_list
                if (flowable := _image_flowable(image_bytes, per_image_width)) is not None
            ]

            if image_flowables:
                flowables.append(Spacer(1, 4))
                if len(image_flowables) == 1:
                    flowables.append(image_flowables[0])
                else:
                    row = Table(
                        [image_flowables],
                        colWidths=[per_image_width] * len(image_flowables),
                        hAlign="CENTER",
                    )
                    row.setStyle(TableStyle([
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("LEFTPADDING", (0, 0), (-1, -1), gap / 2),
                        ("RIGHTPADDING", (0, 0), (-1, -1), gap / 2),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ]))
                    flowables.append(row)
                flowables.append(Spacer(1, 4))

        for option in question.options:
            flowables.append(Paragraph(
                f"({_escape(option.label)}) {_escape(option.option_text)}",
                styles["option"],
            ))

        answer = (getattr(question, "correct_answer", None) or "").strip()
        flowables.append(Paragraph(
            f"Answer: {_escape(answer)}" if answer else "Answer Key: Not Available",
            styles["answer"],
        ))

        # KeepTogether stops a question being orphaned from its own options
        # across a page break.
        story.append(KeepTogether(flowables))

    def make_canvas(*args, **kwargs):
        return _NumberedCanvas(
            *args,
            on_page=lambda c, total: _draw_page_furniture(c, document, header_text, total),
            **kwargs,
        )

    document.build(story, canvasmaker=make_canvas)

    return buffer.getvalue()


__all__ = ["build_paper_pdf"]
