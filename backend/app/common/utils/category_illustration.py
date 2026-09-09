"""
Maps an exam/department/subject name to whichever bundled illustration
actually looks like that subject, instead of every listing page reusing
the same one or two generic images regardless of what it's showing.

This is presentation only - it never invents data, just picks which
already-shipped static asset best matches a name we already have. An
uploaded icon (Exam/Department/Subject.icon_file_id) always wins when
present; this is only the fallback for entities without their own
uploaded image.
"""

# Ordered so a more specific keyword (e.g. "information technology") can
# be listed before a broader one if that's ever needed - first match wins.
_CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("/static/img/illustrations/category-computer-science.svg", [
        "computer science", "information technology", "software", "programming",
        "cse", " it ", " cs ", "data science", "artificial intelligence",
    ]),
    ("/static/img/illustrations/category-mathematics.svg", [
        "mathematic", "statistics", " math",
    ]),
    ("/static/img/illustrations/category-electrical.svg", [
        "electrical", "electronics", "electronic", "instrumentation",
        "communication",
    ]),
    ("/static/img/illustrations/category-mechanical.svg", [
        "mechanical", "production", "industrial", "automobile",
    ]),
    ("/static/img/illustrations/category-civil.svg", [
        "civil", "architecture", "construction",
    ]),
]


def resolve_category_illustration(
    *names: str | None,
    fallback: str = "/static/img/illustrations/exam.webp",
) -> str:
    """
    `names` is typically (subject.name, department.name, exam.name) -
    whichever are available - checked together so e.g. a subject called
    just "Networks" under a "Computer Science" department still resolves
    to the CS illustration.
    """
    haystack = " " + " ".join(name.lower() for name in names if name) + " "

    for illustration_path, keywords in _CATEGORY_KEYWORDS:
        if any(keyword in haystack for keyword in keywords):
            return illustration_path

    return fallback
