"""
Builds the short "what is this page / what's next" copy shown above and
below the real content on every major browsing page (exam, department,
subject, paper, practice, mock test, resources, papers listing, blog).

Every sentence here is assembled from data the caller already has - real
names, real counts, real years - never a fabricated statistic or feature.
A count of 0 is rendered honestly ("no mock tests published yet" rather
than omitted or invented), and an intro/outro is skipped entirely when
there isn't enough real data to say anything meaningful (e.g. an empty
listing page has nothing to summarize).

Each function returns plain strings for a template to render as-is - no
HTML is generated here so there's nothing to escape/trust downstream.
"""
from datetime import datetime


def format_last_updated(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%b %d, %Y")


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


# --------------------------------------------------------------- exam ---

def exam_intro(exam_name: str, department_count: int, papers_count: int, mock_tests_count: int) -> list[str]:
    paragraphs = [
        f"{exam_name} on LearnIn is organized department by department, so you can move straight to the "
        f"discipline you're preparing for instead of digging through one long list of papers."
    ]
    if department_count:
        paragraphs.append(
            f"There {'is' if department_count == 1 else 'are'} currently {_plural(department_count, 'department')} "
            f"published under {exam_name}, each broken down into its own subjects, previous-year papers, and "
            f"practice questions."
        )
    if papers_count or mock_tests_count:
        bits = []
        if papers_count:
            bits.append(_plural(papers_count, "previous-year paper"))
        if mock_tests_count:
            bits.append(_plural(mock_tests_count, "mock test"))
        paragraphs.append(
            f"Across those departments you'll find {' and '.join(bits)} ready to use - work through the real "
            f"papers first, then check your speed and accuracy with a timed mock test."
        )
    return paragraphs


def exam_outro(exam_name: str, department_count: int) -> tuple[str, str, list[dict]]:
    heading = f"Preparing for {exam_name}?"
    if department_count:
        text = (
            f"Pick your department below to see its subjects, then work through the previous-year papers and "
            f"mock tests published for {exam_name}."
        )
    else:
        text = f"Departments for {exam_name} are being added - check back soon for subjects and papers."
    ctas = [{"label": "Browse Previous Year Papers", "url": "/papers"}, {"label": "Explore Mock Tests", "url": "/mock-tests"}]
    return heading, text, ctas


# --------------------------------------------------------- department ---

def department_intro(department_name: str, exam_name: str, subject_count: int) -> list[str]:
    paragraphs = [
        f"{department_name} is one of the departments under {exam_name} on LearnIn, with its subjects "
        f"organized the way they actually appear in the syllabus."
    ]
    if subject_count:
        paragraphs.append(
            f"{_plural(subject_count, 'subject')} {'is' if subject_count == 1 else 'are'} listed for "
            f"{department_name} - open any one of them to see its previous-year papers, practice questions, "
            f"and study resources."
        )
    else:
        paragraphs.append(f"Subjects for {department_name} are being added - check back soon.")
    return paragraphs


def department_outro(department_name: str, subject_count: int) -> tuple[str, str, list[dict]]:
    heading = f"Studying {department_name}?"
    if subject_count:
        text = f"Choose a subject below to start with its previous-year papers and practice questions."
    else:
        text = "New subjects are added regularly - check back soon."
    ctas = [{"label": "Practice by Subject", "url": "/practice"}]
    return heading, text, ctas


# ------------------------------------------------------------- subject ---

def subject_intro(subject_name: str, department_name: str, exam_name: str, paper_count: int, resource_count: int) -> list[str]:
    paragraphs = [
        f"{subject_name} is part of the {department_name} syllabus for {exam_name}. This page collects "
        f"everything LearnIn has for this subject in one place - previous-year papers, practice questions, "
        f"and study resources."
    ]
    if paper_count:
        paragraphs.append(
            f"{_plural(paper_count, 'previous-year paper')} {'is' if paper_count == 1 else 'are'} available for "
            f"{subject_name} - each one can be viewed online, practiced question by question, or downloaded as a PDF."
        )
    if resource_count:
        paragraphs.append(
            f"There {'is' if resource_count == 1 else 'are'} also {_plural(resource_count, 'study resource')} "
            f"for {subject_name}, such as notes and formula sheets, to help you revise alongside the papers."
        )
    paragraphs.append(
        f"Working through {subject_name}'s previous-year papers is the fastest way to learn how {exam_name} "
        f"actually tests this subject - the exact phrasing, the recurring topics, and the difficulty level - "
        f"rather than guessing from a generic question bank. Start with the most recent paper, check your "
        f"answers as you go, and use a mock test once you're comfortable to see how you'd perform under a "
        f"real timer."
    )
    return paragraphs


def subject_outro(subject_name: str, paper_count: int) -> tuple[str, str, list[dict]]:
    heading = f"Ready to start {subject_name}?"
    if paper_count:
        text = (
            f"Open a previous-year paper below to view the questions online, practice them one at a time with "
            f"instant answer checking, or take a timed mock test if one is available."
        )
    else:
        text = f"Papers for {subject_name} are being added - check back soon."
    ctas = [{"label": "All Previous Year Papers", "url": "/papers"}, {"label": "Practice Questions", "url": "/practice"}]
    return heading, text, ctas


# --------------------------------------------------------------- paper ---

def paper_intro(paper_title: str, year: int, subject_name: str, department_name: str, exam_name: str, total_questions: int, duration: int | None, has_answer_key: bool) -> list[str]:
    paragraphs = [
        f"This is the {year} {subject_name} paper for {department_name}, {exam_name} - a real previous-year "
        f"question paper, not a practice set written to imitate one."
    ]
    facts = []
    if total_questions:
        facts.append(_plural(total_questions, "question"))
    if duration:
        facts.append(f"a suggested duration of {duration} minutes")
    if facts:
        paragraphs.append(f"It has {' and '.join(facts)}, and you can view or download the original question paper below.")
    if has_answer_key:
        paragraphs.append("An official answer key is also available for this paper, so you can check your work after attempting it.")
    paragraphs.append(
        f"Solving an actual {year} paper - rather than a set of questions written to resemble one - is one of "
        f"the most reliable ways to gauge where you stand for {subject_name}. Read the question paper first if "
        f"you want to attempt it under exam-like conditions, or open practice mode below to go through it one "
        f"question at a time with instant answer checking."
    )
    return paragraphs


def paper_outro(year: int, subject_name: str, mock_test_count: int, paper_url: str, subject_url: str) -> tuple[str, str, list[dict]]:
    heading = f"Done with the {year} paper?"
    if mock_test_count:
        text = (
            f"You can practice these questions one at a time online, or take one of the timed mock tests below "
            f"built from this paper to simulate real exam conditions."
        )
    else:
        text = "Practice these questions one at a time online with instant answer checking."
    ctas = [
        {"label": "Practice This Paper", "url": f"{paper_url}/practice"},
        {"label": f"More {subject_name} Papers", "url": subject_url},
    ]
    return heading, text, ctas


# -------------------------------------------------- mock test result ---

def mock_test_result_intro(
    mock_test_title: str,
    subject_name: str,
    accuracy: float | None,
    correct_count: int,
    total_questions: int,
) -> list[str]:
    paragraphs = [
        f"This is your result for {mock_test_title}. Below you'll find your score, a subject-wise accuracy "
        f"breakdown, and a full review of every question - your answer, the correct one, and the explanation "
        f"where one is available."
    ]
    if accuracy is not None:
        paragraphs.append(
            f"You answered {_plural(correct_count, 'question')} correctly out of {total_questions} attempted "
            f"or skipped, for {accuracy}% accuracy on {subject_name}. Use the review section below to see "
            f"exactly which questions to revisit, not just how many you got right."
        )
    else:
        paragraphs.append(
            f"None of your answers on this attempt could be scored for accuracy - check the review section "
            f"below to see how each question was answered."
        )
    return paragraphs


# ----------------------------------------------------- listing pages ---

def paper_list_intro(total: int, filters_active: bool) -> list[str]:
    if filters_active:
        return [
            f"Showing {_plural(total, 'previous-year paper')} matching your current filters. Adjust the exam, "
            f"subject, or year above to narrow or widen the results."
        ]
    return [
        "Every previous-year question paper on LearnIn is listed here, sourced directly from the papers "
        "published under each exam's subjects.",
        f"There {'is' if total == 1 else 'are'} currently {_plural(total, 'paper')} available - use the filters "
        "above to find papers for a specific exam, department, subject, or year, or search by title.",
    ]


def mock_test_list_intro(total: int, filters_active: bool) -> list[str]:
    if filters_active:
        return [f"Showing {_plural(total, 'mock test')} matching your current filters."]
    return [
        "Mock tests on LearnIn are timed and built from real previous-year papers, with instant scoring and a "
        "subject-wise breakdown once you submit.",
        f"There {'is' if total == 1 else 'are'} currently {_plural(total, 'mock test')} available - filter by "
        "exam, department, or subject to find one for your preparation.",
    ]


def practice_list_intro(total: int, filters_active: bool) -> list[str]:
    if filters_active:
        return [f"Showing {_plural(total, 'subject')} matching your current filters."]
    return [
        "Practice mode lets you work through a subject's previous-year questions one at a time, with instant "
        "answer checking - useful for building accuracy before you attempt a timed mock test.",
        f"{_plural(total, 'subject')} {'is' if total == 1 else 'are'} currently available to practice - pick one "
        "below, or filter by exam and department to narrow the list.",
    ]


def exam_list_intro(total: int) -> list[str]:
    return [
        "LearnIn organizes each exam into departments, subjects, previous-year papers, mock tests, and study "
        "resources, so you can prepare one subject at a time instead of searching for scattered material.",
        f"{_plural(total, 'exam')} {'is' if total == 1 else 'are'} currently available - choose one below to see "
        "what's published for it.",
    ]


def blog_list_intro(total: int, category: str | None) -> list[str]:
    if category:
        return [f"Showing {_plural(total, 'article')} in {category}."]
    return [
        "Study tips, exam strategy, and preparation guidance from the LearnIn team, alongside the previous-year "
        f"papers, mock tests, and practice questions elsewhere on the site.",
    ]


def exam_list_outro() -> tuple[str, str, list[dict]]:
    return (
        "Not sure where to start?",
        "Pick the exam you're preparing for above to see its departments and subjects, or jump straight into "
        "practice questions or a timed mock test.",
        [{"label": "Practice Questions", "url": "/practice"}, {"label": "Mock Tests", "url": "/mock-tests"}],
    )


def paper_list_outro() -> tuple[str, str, list[dict]]:
    return (
        "Looking for something specific?",
        "Use the filters above to narrow papers down by exam, subject, or year, or switch to practice mode to "
        "work through questions one at a time.",
        [{"label": "Practice Questions", "url": "/practice"}, {"label": "Mock Tests", "url": "/mock-tests"}],
    )


def mock_test_list_outro() -> tuple[str, str, list[dict]]:
    return (
        "Want to build accuracy first?",
        "Work through a subject's previous-year questions in practice mode before you take a timed mock test.",
        [{"label": "Practice Questions", "url": "/practice"}, {"label": "Previous Year Papers", "url": "/papers"}],
    )


def practice_list_outro() -> tuple[str, str, list[dict]]:
    return (
        "Ready for a timed test?",
        "Once you're comfortable with a subject, take a mock test to see how you'd perform under real exam conditions.",
        [{"label": "Mock Tests", "url": "/mock-tests"}, {"label": "Previous Year Papers", "url": "/papers"}],
    )


def blog_list_outro() -> tuple[str, str, list[dict]]:
    return (
        "Ready to start preparing?",
        "Pick your exam to see its previous-year papers, practice questions, and mock tests.",
        [{"label": "Explore Exams", "url": "/exams"}],
    )
