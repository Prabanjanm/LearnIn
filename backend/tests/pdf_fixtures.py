"""
Synthetic PDFs built at test time with PyMuPDF, so the suite needs no
binary fixture files checked into the repo.
"""
import pymupdf


def text_pdf(pages: list[str], rotate: int = 0) -> bytes:
    """A normal, text-layer PDF - one page per string."""
    document = pymupdf.open()

    for body in pages:
        page = document.new_page()
        page.insert_textbox(
            pymupdf.Rect(40, 40, 555, 800),
            body,
            fontsize=11,
            fontname="helv",
            rotate=rotate,
        )

    content = document.tobytes()
    document.close()
    return content


def scanned_pdf(page_count: int = 2) -> bytes:
    """
    A PDF with no text layer at all - just a raster image per page, which is
    what a scan looks like to an extractor.
    """
    document = pymupdf.open()

    for _ in range(page_count):
        page = document.new_page()
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 260))
        pixmap.set_rect(pixmap.irect, (240, 240, 240))
        page.insert_image(pymupdf.Rect(50, 50, 450, 700), pixmap=pixmap)

    content = document.tobytes()
    document.close()
    return content


def empty_pdf() -> bytes:
    """
    A structurally valid PDF whose page tree is empty.

    Hand-written rather than built with PyMuPDF, which refuses to save a
    zero-page document - but real files like this do turn up (truncated
    exports, broken generators), which is exactly what validation must catch.
    """
    body = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\n"
        b"trailer<</Root 1 0 R/Size 3>>\n"
        b"%%EOF\n"
    )
    return body


def blank_pages_pdf(page_count: int = 2) -> bytes:
    """Pages exist but carry no text and no images."""
    document = pymupdf.open()
    for _ in range(page_count):
        document.new_page()
    content = document.tobytes()
    document.close()
    return content


def encrypted_pdf(password: str = "secret") -> bytes:
    """A password-protected PDF."""
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Locked content", fontsize=12)

    content = document.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw=password,
        user_pw=password,
    )
    document.close()
    return content


def corrupted_pdf() -> bytes:
    """Starts like a PDF (so upload_policy passes) but is not one."""
    return b"%PDF-1.4\nthis is definitely not a valid pdf body\n%%EOF"


def watermarked_pdf(pages: int = 3) -> bytes:
    """
    Real body text plus a repeated, rotated, light-grey watermark that also
    matches the known-source deny list.
    """
    document = pymupdf.open()

    for index in range(pages):
        page = document.new_page()
        page.insert_textbox(
            pymupdf.Rect(40, 120, 555, 700),
            f"{index + 1}. Genuine question number {index + 1} on this page?\n"
            f"A) option a{index}\nB) option b{index}\n"
            f"C) option c{index}\nD) option d{index}",
            fontsize=11,
            fontname="helv",
        )
        page.insert_text(
            (300, 760),
            "Downloaded from www.example-papers.com",
            fontsize=14,
            # PyMuPDF's insert_text only accepts multiples of 90; 90 is
            # still "rotated" for the watermark heuristic's purposes.
            rotate=90,
            color=(0.88, 0.88, 0.88),
        )

    content = document.tobytes()
    document.close()
    return content


SAMPLE_PAPER_PAGE_ONE = """1. What is the time complexity of binary search?
A) O(n)
B) O(log n)
C) O(n log n)
D) O(1)

2. Which data structure uses FIFO ordering?
A) Stack
B) Queue
C) Tree
D) Graph
"""

SAMPLE_PAPER_PAGE_TWO = """3. Which of the following is a stable sorting algorithm?
A) Quick sort
B) Heap sort
C) Merge sort
D) Selection sort

4. A relation is in BCNF if for every functional dependency X to Y,
X is a superkey of the relation. Which normal form does this imply?
A) First normal form
B) Second normal form
C) Third normal form
D) Fourth normal form
"""


def sample_paper_pdf() -> bytes:
    return text_pdf([SAMPLE_PAPER_PAGE_ONE, SAMPLE_PAPER_PAGE_TWO])


def pdf_with_embedded_diagram() -> bytes:
    """
    Two questions on one page, with a real embedded raster image sitting
    between question 1's own text and its options - exactly the "text ->
    diagram -> options" shape a real exam question uses. Question 2 has no
    image at all, so this also exercises that an image never bleeds into a
    neighbouring question.
    """
    document = pymupdf.open()
    page = document.new_page()

    page.insert_textbox(
        pymupdf.Rect(40, 40, 555, 90),
        "1. Refer to the diagram below. What shape is shown?",
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

    page.insert_textbox(
        pymupdf.Rect(40, 400, 555, 480),
        "2. Which of these is not a primary colour?\n"
        "A) red\nB) green\nC) orange\nD) blue",
        fontsize=11, fontname="helv",
    )

    content = document.tobytes()
    document.close()
    return content


def pdf_with_vector_diagram() -> bytes:
    """One question with a real vector drawing (not an embedded image)
    between its text and its options."""
    document = pymupdf.open()
    page = document.new_page()

    page.insert_textbox(
        pymupdf.Rect(40, 40, 555, 90),
        "1. What does the triangle below represent?",
        fontsize=11, fontname="helv",
    )

    shape = page.new_shape()
    shape.draw_polyline([
        pymupdf.Point(240, 130), pymupdf.Point(300, 220), pymupdf.Point(180, 220), pymupdf.Point(240, 130),
    ])
    shape.finish(color=(0, 0, 0), fill=None, width=2)
    shape.commit()

    page.insert_textbox(
        pymupdf.Rect(40, 260, 555, 340),
        "A) a right triangle\nB) an equilateral triangle\nC) a scalene triangle\nD) a square",
        fontsize=11, fontname="helv",
    )

    content = document.tobytes()
    document.close()
    return content


def pdf_with_unaccounted_gap() -> bytes:
    """
    One question whose own text leaves a large vertical gap between its
    question line and its options, with nothing (no embedded image, no
    vector drawing) placed there - the geometric fallback case: something is
    clearly meant to be there, but no recognisable object was found.
    """
    document = pymupdf.open()
    page = document.new_page()

    page.insert_textbox(
        pymupdf.Rect(40, 40, 555, 90),
        "1. Study the (unreadable/blank) figure below and answer.",
        fontsize=11, fontname="helv",
    )
    page.insert_textbox(
        pymupdf.Rect(40, 400, 555, 480),
        "A) one\nB) two\nC) three\nD) four",
        fontsize=11, fontname="helv",
    )

    content = document.tobytes()
    document.close()
    return content
