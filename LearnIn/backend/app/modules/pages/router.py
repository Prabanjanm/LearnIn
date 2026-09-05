from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import (
    AlreadyExistsException,
    InvalidCredentialsException,
    NotFoundException,
)
from app.core.config import settings
from app.core.database import get_db
from app.common.rate_limit import rate_limit
from app.common.utils.markdown_render import render_markdown
from app.core.security import create_access_token
from app.modules.blog.service import blog_service
from app.modules.department.service import department_service
from app.modules.exam.service import exam_service
from app.modules.mock_test.service import mock_test_service
from app.modules.mock_test_attempt.service import mock_test_attempt_service
from app.modules.mock_test_question.service import mock_test_question_service
from app.modules.paper.service import paper_service
from app.modules.resource.service import resource_service
from app.modules.search.service import search_service
from app.modules.student.dependencies import STUDENT_ACCESS_TOKEN_COOKIE_NAME, get_optional_student
from app.modules.student.model import Student
from app.modules.student.service import student_service
from app.modules.subject.service import subject_service

from .resolvers import resolve_department, resolve_exam, resolve_paper, resolve_subject

router = APIRouter(tags=["Pages"])

templates = Jinja2Templates(directory="app/templates")


def _not_found(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="pages/404.html",
        context={},
        status_code=404,
    )


# ----------------------------------------------------------- account -----

@router.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request, student: Student | None = Depends(get_optional_student)):
    if student is not None:
        return RedirectResponse("/dashboard", status_code=303)

    return templates.TemplateResponse(request=request, name="account/signup.html", context={"error": None})


@router.post("/signup", response_class=HTMLResponse, dependencies=[Depends(rate_limit(10, 60))])
def signup_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        student = student_service.signup(db, email, password, full_name or None)
    except AlreadyExistsException as exc:
        return templates.TemplateResponse(
            request=request,
            name="account/signup.html",
            context={"error": str(exc)},
            status_code=409,
        )

    return _login_response(student, "/dashboard")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, student: Student | None = Depends(get_optional_student)):
    if student is not None:
        return RedirectResponse("/dashboard", status_code=303)

    return templates.TemplateResponse(request=request, name="account/login.html", context={"error": None})


@router.post("/login", response_class=HTMLResponse, dependencies=[Depends(rate_limit(10, 60))])
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        student = student_service.authenticate(db, email, password)
    except InvalidCredentialsException:
        return templates.TemplateResponse(
            request=request,
            name="account/login.html",
            context={"error": "Invalid email or password"},
            status_code=401,
        )

    return _login_response(student, "/dashboard")


def _login_response(student: Student, redirect_to: str) -> RedirectResponse:
    token = create_access_token(subject=student.email)
    response = RedirectResponse(redirect_to, status_code=303)
    response.set_cookie(
        key=STUDENT_ACCESS_TOKEN_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=not settings.DEBUG,
        max_age=60 * 60 * 24 * 30,
    )
    return response


@router.get("/logout")
def logout_page():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(STUDENT_ACCESS_TOKEN_COOKIE_NAME)
    return response


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, student: Student | None = Depends(get_optional_student), db: Session = Depends(get_db)):
    if student is None:
        return RedirectResponse("/login", status_code=303)

    attempts = mock_test_attempt_service.get_by_student(db, student.id)

    graded_attempts = [a for a in attempts if (a.correct_count + a.incorrect_count) > 0]
    average_accuracy = (
        round(sum(100 * a.correct_count / (a.correct_count + a.incorrect_count) for a in graded_attempts) / len(graded_attempts), 1)
        if graded_attempts
        else None
    )

    weak_subjects = mock_test_attempt_service.get_weak_subjects(db, student.id)
    for entry in weak_subjects:
        subject = entry["subject"]
        entry["url"] = f"/{subject.department.exam.slug}/{subject.department.slug}/{subject.slug}"

    return templates.TemplateResponse(
        request=request,
        name="account/dashboard.html",
        context={
            "student": student,
            "attempts": attempts,
            "attempts_count": len(attempts),
            "average_accuracy": average_accuracy,
            "weak_subjects": weak_subjects,
        },
    )


# ------------------------------------------------------------ static -----

@router.get("/about", response_class=HTMLResponse)
def about_page(request: Request):
    return templates.TemplateResponse(request=request, name="pages/about.html", context={})


@router.get("/contact", response_class=HTMLResponse)
def contact_page(request: Request):
    return templates.TemplateResponse(request=request, name="pages/contact.html", context={})


@router.get("/privacy", response_class=HTMLResponse)
def privacy_page(request: Request):
    return templates.TemplateResponse(request=request, name="pages/privacy.html", context={})


@router.get("/disclaimer", response_class=HTMLResponse)
def disclaimer_page(request: Request):
    return templates.TemplateResponse(request=request, name="pages/disclaimer.html", context={})


@router.get("/terms", response_class=HTMLResponse)
def terms_page(request: Request):
    return templates.TemplateResponse(request=request, name="pages/terms.html", context={})


# --------------------------------------------------------------- SEO -----

@router.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /api/\n"
        "Disallow: /dashboard\n"
        "Disallow: /login\n"
        "Disallow: /signup\n"
        "Disallow: /logout\n"
        "Disallow: */mock-test/*/result/*\n"
        f"Sitemap: {base_url}/sitemap.xml\n"
    )


@router.get("/sitemap.xml")
def sitemap_xml(request: Request, db: Session = Depends(get_db)):
    base_url = str(request.base_url).rstrip("/")
    urls = [
        base_url + "/",
        base_url + "/exams",
        base_url + "/papers",
        base_url + "/mock-tests",
        base_url + "/practice",
        base_url + "/blogs",
        base_url + "/about",
        base_url + "/contact",
        base_url + "/privacy",
        base_url + "/terms",
        base_url + "/disclaimer",
    ]

    # Each of these already returns PUBLISHED-only rows.
    for exam in exam_service.get_published(db):
        urls.append(f"{base_url}/{exam.slug}")

        for department in department_service.get_published_by_exam(db, exam.id):
            urls.append(f"{base_url}/{exam.slug}/{department.slug}")

            for subject in subject_service.get_published_by_department(db, department.id):
                subject_url = f"{base_url}/{exam.slug}/{department.slug}/{subject.slug}"
                urls.append(subject_url)

                for paper in paper_service.get_published_by_subject(db, subject.id):
                    urls.append(f"{subject_url}/{paper.year}")

    published_blogs, _total = blog_service.get_published(db, page=1, page_size=10_000)
    for blog in published_blogs:
        urls.append(f"{base_url}/blogs/{blog.slug}")

    body = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in urls:
        body.append(f"<url><loc>{url}</loc></url>")
    body.append("</urlset>")

    return Response(content="".join(body), media_type="application/xml")


# -------------------------------------------------------------- blog -----

@router.get("/blogs", response_class=HTMLResponse)
def blog_list_page(
    request: Request,
    category: str | None = None,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    items, total = blog_service.get_published(db, category, page, 12)

    blog_cards = [
        {
            "title": blog.title,
            "url": f"/blogs/{blog.slug}",
            "meta": blog.category,
        }
        for blog in items
    ]

    extra_query = f"&category={category}" if category else ""

    return templates.TemplateResponse(
        request=request,
        name="blog/blog.html",
        context={
            "blog_cards": blog_cards,
            "total": total,
            "page": page,
            "has_previous": page > 1,
            "has_next": total > page * 12,
            "extra_query": extra_query,
            "category": category,
        },
    )


@router.get("/blogs/{slug}", response_class=HTMLResponse)
def blog_detail_page(slug: str, request: Request, db: Session = Depends(get_db)):
    try:
        blog = blog_service.get_published_by_slug(db, slug)
    except NotFoundException:
        return _not_found(request)

    return templates.TemplateResponse(
        request=request,
        name="blog/detail.html",
        context={"blog": blog, "content_html": render_markdown(blog.content)},
    )


# ------------------------------------------------------------ search -----

@router.get("/search", response_class=HTMLResponse)
def search_page(request: Request, q: str = "", db: Session = Depends(get_db)):
    results = search_service.search(db, q) if q.strip() else None

    return templates.TemplateResponse(
        request=request,
        name="search/search.html",
        context={"query": q, "results": results},
    )


# ------------------------------------------------------ exam hierarchy ---

@router.get("/exams", response_class=HTMLResponse)
def exam_list_page(request: Request, db: Session = Depends(get_db)):
    exams = exam_service.get_published(db)

    exam_cards = [
        {
            "title": exam.name,
            "url": f"/{exam.slug}",
            "meta": f"{len(department_service.get_published_by_exam(db, exam.id))} departments",
        }
        for exam in exams
    ]

    return templates.TemplateResponse(
        request=request,
        name="exam/exam_list.html",
        context={
            "exam_cards": exam_cards,
            "breadcrumbs": [{"label": "Exams", "url": None}],
        },
    )


PAPER_LIST_PAGE_SIZE = 20


@router.get("/papers", response_class=HTMLResponse)
def paper_list_page(
    request: Request,
    q: str = "",
    exam_id: int | None = None,
    department_id: int | None = None,
    subject_id: int | None = None,
    year: int | None = None,
    answer_key: str | None = None,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    has_answer_key = {"available": True, "unavailable": False}.get(answer_key)

    papers, total = paper_service.get_filtered(
        db,
        exam_id=exam_id,
        department_id=department_id,
        subject_id=subject_id,
        year=year,
        has_answer_key=has_answer_key,
        term=q.strip() or None,
        page=page,
        page_size=PAPER_LIST_PAGE_SIZE,
    )

    paper_rows = [
        {
            "title": paper.title,
            "url": f"/{paper.subject.department.exam.slug}/{paper.subject.department.slug}/{paper.subject.slug}/{paper.year}",
            "exam_name": paper.subject.department.exam.name,
            "department_name": paper.subject.department.name,
            "subject_name": paper.subject.name,
            "year": paper.year,
            "total_questions": paper.total_questions,
            "duration": paper.duration,
            "has_answer_key": bool(paper.answer_file_id),
            "question_file_id": paper.question_file_id,
            "answer_file_id": paper.answer_file_id,
        }
        for paper in papers
    ]

    # Filter dropdown options - only real data. Departments/subjects are
    # scoped to the selected exam/department so the dropdowns never offer
    # a combination that would return zero results.
    exams = exam_service.get_published(db)
    departments = department_service.get_published_by_exam(db, exam_id) if exam_id else []
    subjects = subject_service.get_published_by_department(db, department_id) if department_id else []
    years = paper_service.get_distinct_years(db)

    query_params = {
        "q": q, "exam_id": exam_id, "department_id": department_id,
        "subject_id": subject_id, "year": year, "answer_key": answer_key,
    }
    extra_query = "".join(f"&{k}={v}" for k, v in query_params.items() if v not in (None, ""))

    return templates.TemplateResponse(
        request=request,
        name="paper/paper_list.html",
        context={
            "papers": paper_rows,
            "total": total,
            "page": page,
            "has_previous": page > 1,
            "has_next": total > page * PAPER_LIST_PAGE_SIZE,
            "extra_query": extra_query,
            "exams": exams,
            "departments": departments,
            "subjects": subjects,
            "years": years,
            "filters": {
                "q": q, "exam_id": exam_id, "department_id": department_id,
                "subject_id": subject_id, "year": year, "answer_key": answer_key,
            },
            "breadcrumbs": [{"label": "Previous Year Papers", "url": None}],
        },
    )


MOCK_TEST_LIST_PAGE_SIZE = 20


@router.get("/mock-tests", response_class=HTMLResponse)
def mock_test_list_page(
    request: Request,
    q: str = "",
    exam_id: int | None = None,
    department_id: int | None = None,
    subject_id: int | None = None,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    mock_tests, total = mock_test_service.get_filtered(
        db,
        exam_id=exam_id,
        department_id=department_id,
        subject_id=subject_id,
        term=q.strip() or None,
        page=page,
        page_size=MOCK_TEST_LIST_PAGE_SIZE,
    )

    mock_test_rows = [
        {
            "title": mt.title,
            "url": (
                f"/{mt.paper.subject.department.exam.slug}/{mt.paper.subject.department.slug}"
                f"/{mt.paper.subject.slug}/{mt.paper.year}/mock-test/{mt.id}"
            ),
            "exam_name": mt.paper.subject.department.exam.name,
            "subject_name": mt.paper.subject.name,
            "total_questions": mt.total_questions,
            "duration": mt.duration,
            "total_marks": mt.total_marks,
        }
        for mt in mock_tests
    ]

    exams = exam_service.get_published(db)
    departments = department_service.get_published_by_exam(db, exam_id) if exam_id else []
    subjects = subject_service.get_published_by_department(db, department_id) if department_id else []

    query_params = {"q": q, "exam_id": exam_id, "department_id": department_id, "subject_id": subject_id}
    extra_query = "".join(f"&{k}={v}" for k, v in query_params.items() if v not in (None, ""))

    return templates.TemplateResponse(
        request=request,
        name="mock_test/mock_test_list.html",
        context={
            "mock_tests": mock_test_rows,
            "total": total,
            "page": page,
            "has_previous": page > 1,
            "has_next": total > page * MOCK_TEST_LIST_PAGE_SIZE,
            "extra_query": extra_query,
            "exams": exams,
            "departments": departments,
            "subjects": subjects,
            "filters": {"q": q, "exam_id": exam_id, "department_id": department_id, "subject_id": subject_id},
            "breadcrumbs": [{"label": "Mock Tests", "url": None}],
        },
    )


PRACTICE_LIST_PAGE_SIZE = 24


@router.get("/practice", response_class=HTMLResponse)
def practice_list_page(
    request: Request,
    q: str = "",
    exam_id: int | None = None,
    department_id: int | None = None,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    """
    Practice questions belong to a specific paper (Question.paper_id),
    not a standalone question bank, so there's no honest way to browse
    "all questions across LearnIn" as one flat list without inventing an
    unsupported cross-paper concept. Instead this discovers subjects -
    a real entity - each of which already leads (via its own page) to
    every paper with a "Practice Online" action. That keeps Exam -> Subject
    -> Practice a short, real path without fabricating a topic/question
    bank entity the schema doesn't have.
    """
    subjects, total = subject_service.get_filtered(
        db,
        exam_id=exam_id,
        department_id=department_id,
        term=q.strip() or None,
        page=page,
        page_size=PRACTICE_LIST_PAGE_SIZE,
    )

    subject_rows = [
        {
            "title": subject.name,
            "url": f"/{subject.department.exam.slug}/{subject.department.slug}/{subject.slug}",
            "meta": f"{subject.department.exam.name} · {subject.department.name}",
        }
        for subject in subjects
    ]

    exams = exam_service.get_published(db)
    departments = department_service.get_published_by_exam(db, exam_id) if exam_id else []

    query_params = {"q": q, "exam_id": exam_id, "department_id": department_id}
    extra_query = "".join(f"&{k}={v}" for k, v in query_params.items() if v not in (None, ""))

    return templates.TemplateResponse(
        request=request,
        name="subject/practice_list.html",
        context={
            "subjects": subject_rows,
            "total": total,
            "page": page,
            "has_previous": page > 1,
            "has_next": total > page * PRACTICE_LIST_PAGE_SIZE,
            "extra_query": extra_query,
            "exams": exams,
            "departments": departments,
            "filters": {"q": q, "exam_id": exam_id, "department_id": department_id},
            "breadcrumbs": [{"label": "Practice", "url": None}],
        },
    )


@router.get("/{exam_slug}", response_class=HTMLResponse)
def exam_page(exam_slug: str, request: Request, db: Session = Depends(get_db)):
    try:
        ctx = resolve_exam(db, exam_slug)
    except NotFoundException:
        return _not_found(request)

    departments = department_service.get_published_by_exam(db, ctx.exam.id)
    department_cards = [
        {
            "title": d.name,
            "url": f"/{ctx.exam.slug}/{d.slug}",
            "meta": f"{d.code} · {len(subject_service.get_published_by_department(db, d.id))} subjects",
        }
        for d in departments
    ]

    return templates.TemplateResponse(
        request=request,
        name="exam/exam.html",
        context={
            "exam": ctx.exam,
            "department_cards": department_cards,
            "breadcrumbs": ctx.breadcrumbs_with_current(ctx.exam.name),
        },
    )


@router.get("/{exam_slug}/{department_slug}", response_class=HTMLResponse)
def department_page(
    exam_slug: str,
    department_slug: str,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        ctx = resolve_department(db, exam_slug, department_slug)
    except NotFoundException:
        return _not_found(request)

    subjects = subject_service.get_published_by_department(db, ctx.department.id)
    subject_cards = [
        {
            "title": s.name,
            "url": f"/{ctx.exam.slug}/{ctx.department.slug}/{s.slug}",
            "meta": f"{len(paper_service.get_published_by_subject(db, s.id))} papers",
        }
        for s in subjects
    ]

    return templates.TemplateResponse(
        request=request,
        name="department/department.html",
        context={
            "exam": ctx.exam,
            "department": ctx.department,
            "subject_cards": subject_cards,
            "breadcrumbs": ctx.breadcrumbs_with_current(ctx.department.name),
        },
    )


@router.get("/{exam_slug}/{department_slug}/{subject_slug}", response_class=HTMLResponse)
def subject_page(
    exam_slug: str,
    department_slug: str,
    subject_slug: str,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        ctx = resolve_subject(db, exam_slug, department_slug, subject_slug)
    except NotFoundException:
        return _not_found(request)

    base_url = f"/{ctx.exam.slug}/{ctx.department.slug}/{ctx.subject.slug}"

    papers = paper_service.get_published_by_subject(db, ctx.subject.id)
    paper_cards = [
        {
            "title": p.title,
            "url": f"{base_url}/{p.year}",
            "meta": f"{p.year} · {p.total_questions} questions",
        }
        for p in papers
    ]

    resources = resource_service.get_published_by_subject(db, ctx.subject.id)
    resource_cards = [
        {
            "title": r.title,
            "url": f"https://drive.google.com/file/d/{r.google_drive_file_id}/view",
            "meta": r.resource_type,
            "target_blank": True,
        }
        for r in resources
    ]

    return templates.TemplateResponse(
        request=request,
        name="subject/subject.html",
        context={
            "exam": ctx.exam,
            "department": ctx.department,
            "subject": ctx.subject,
            "paper_cards": paper_cards,
            "resource_cards": resource_cards,
            "breadcrumbs": ctx.breadcrumbs_with_current(ctx.subject.name),
        },
    )


@router.get("/{exam_slug}/{department_slug}/{subject_slug}/{year}", response_class=HTMLResponse)
def paper_page(
    exam_slug: str,
    department_slug: str,
    subject_slug: str,
    year: int,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        ctx = resolve_paper(db, exam_slug, department_slug, subject_slug, year)
    except NotFoundException:
        return _not_found(request)

    mock_tests = mock_test_service.get_published_by_paper(db, ctx.paper.id)
    mock_test_cards = [
        {
            "title": mt.title,
            "url": f"{ctx.paper_url()}/mock-test/{mt.id}",
            "meta": f"{mt.total_questions} questions · {mt.duration} min",
        }
        for mt in mock_tests
    ]

    return templates.TemplateResponse(
        request=request,
        name="paper/paper.html",
        context={
            "exam": ctx.exam,
            "department": ctx.department,
            "subject": ctx.subject,
            "paper": ctx.paper,
            "mock_test_cards": mock_test_cards,
            "breadcrumbs": ctx.breadcrumbs_with_current(ctx.paper.year),
        },
    )


@router.get("/{exam_slug}/{department_slug}/{subject_slug}/{year}/practice", response_class=HTMLResponse)
def practice_page(
    exam_slug: str,
    department_slug: str,
    subject_slug: str,
    year: int,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        ctx = resolve_paper(db, exam_slug, department_slug, subject_slug, year)
    except NotFoundException:
        return _not_found(request)

    breadcrumbs = ctx.breadcrumb_trail() + [
        {"label": ctx.paper.year, "url": ctx.paper_url()},
        {"label": "Practice", "url": None},
    ]

    return templates.TemplateResponse(
        request=request,
        name="paper/practice.html",
        context={
            "exam": ctx.exam,
            "department": ctx.department,
            "subject": ctx.subject,
            "paper": ctx.paper,
            "breadcrumbs": breadcrumbs,
        },
    )


@router.get(
    "/{exam_slug}/{department_slug}/{subject_slug}/{year}/mock-test/{mock_test_id}",
    response_class=HTMLResponse,
)
def mock_test_page(
    exam_slug: str,
    department_slug: str,
    subject_slug: str,
    year: int,
    mock_test_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        ctx = resolve_paper(db, exam_slug, department_slug, subject_slug, year)
        mock_test = mock_test_service.get_published_by_id(db, mock_test_id)
    except NotFoundException:
        return _not_found(request)

    if mock_test.paper_id != ctx.paper.id:
        return _not_found(request)

    question_count = len(mock_test_question_service.get_by_mock_test(db, mock_test_id))

    breadcrumbs = ctx.breadcrumb_trail() + [
        {"label": ctx.paper.year, "url": ctx.paper_url()},
        {"label": mock_test.title, "url": None},
    ]

    return templates.TemplateResponse(
        request=request,
        name="mock_test/mock_test.html",
        context={
            "exam": ctx.exam,
            "department": ctx.department,
            "subject": ctx.subject,
            "paper": ctx.paper,
            "mock_test": mock_test,
            "question_count": question_count,
            "breadcrumbs": breadcrumbs,
        },
    )


@router.get(
    "/{exam_slug}/{department_slug}/{subject_slug}/{year}/mock-test/{mock_test_id}/result/{attempt_id}",
    response_class=HTMLResponse,
)
def mock_test_result_page(
    exam_slug: str,
    department_slug: str,
    subject_slug: str,
    year: int,
    mock_test_id: int,
    attempt_id: int,
    request: Request,
    db: Session = Depends(get_db),
    student: Student | None = Depends(get_optional_student),
):
    try:
        ctx = resolve_paper(db, exam_slug, department_slug, subject_slug, year)
        mock_test = mock_test_service.get_published_by_id(db, mock_test_id)
        attempt = mock_test_attempt_service.get_with_answers(db, attempt_id)
    except NotFoundException:
        return _not_found(request)

    if mock_test.paper_id != ctx.paper.id or attempt.mock_test_id != mock_test.id:
        return _not_found(request)

    # An attempt submitted while logged in belongs to that student only -
    # anyone else (including a different logged-in student) gets a 404,
    # not a peek at someone else's answers/score. An anonymous attempt
    # (student_id is None) has no owner to check against, so it stays
    # visible to whoever holds the link, same as before login existed.
    if attempt.student_id is not None and (student is None or student.id != attempt.student_id):
        return _not_found(request)

    accuracy = round(100 * attempt.correct_count / (attempt.correct_count + attempt.incorrect_count), 1) \
        if (attempt.correct_count + attempt.incorrect_count) > 0 else None

    breadcrumbs = ctx.breadcrumb_trail() + [
        {"label": ctx.paper.year, "url": ctx.paper_url()},
        {"label": mock_test.title, "url": f"{ctx.paper_url()}/mock-test/{mock_test.id}"},
        {"label": "Result", "url": None},
    ]

    # "What should you practice next?" only has real, personalized data to
    # show for a logged-in student with enough graded history (same
    # min-answered safeguard as the dashboard - see get_weak_subjects).
    # A mock test's questions all come from one paper, which belongs to
    # exactly one subject, so there is no multi-subject breakdown to
    # compute here - only this one subject's performance is real.
    weak_subjects = []
    if student is not None:
        weak_subjects = mock_test_attempt_service.get_weak_subjects(db, student.id)
        for entry in weak_subjects:
            weak_subject = entry["subject"]
            entry["url"] = f"/{weak_subject.department.exam.slug}/{weak_subject.department.slug}/{weak_subject.slug}"

    return templates.TemplateResponse(
        request=request,
        name="mock_test/result.html",
        context={
            "exam": ctx.exam,
            "department": ctx.department,
            "subject": ctx.subject,
            "paper": ctx.paper,
            "mock_test": mock_test,
            "attempt": attempt,
            "accuracy": accuracy,
            "student": student,
            "weak_subjects": weak_subjects,
            "breadcrumbs": breadcrumbs,
        },
    )
