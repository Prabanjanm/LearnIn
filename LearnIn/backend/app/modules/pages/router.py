import markdown
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import NotFoundException
from app.core.database import get_db
from app.modules.blog.service import blog_service
from app.modules.department.service import department_service
from app.modules.exam.service import exam_service
from app.modules.mock_test.service import mock_test_service
from app.modules.mock_test_question.service import mock_test_question_service
from app.modules.paper.service import paper_service
from app.modules.resource.service import resource_service
from app.modules.search.service import search_service
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


# --------------------------------------------------------------- SEO -----

@router.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /api/\n"
        f"Sitemap: {base_url}/sitemap.xml\n"
    )


@router.get("/sitemap.xml")
def sitemap_xml(request: Request, db: Session = Depends(get_db)):
    base_url = str(request.base_url).rstrip("/")
    urls = [base_url + "/", base_url + "/blogs", base_url + "/search"]

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
        context={"blog": blog, "content_html": markdown.markdown(blog.content)},
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

@router.get("/{exam_slug}", response_class=HTMLResponse)
def exam_page(exam_slug: str, request: Request, db: Session = Depends(get_db)):
    try:
        ctx = resolve_exam(db, exam_slug)
    except NotFoundException:
        return _not_found(request)

    departments = department_service.get_published_by_exam(db, ctx.exam.id)
    department_cards = [
        {"title": d.name, "url": f"/{ctx.exam.slug}/{d.slug}", "meta": d.code}
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
        {"title": s.name, "url": f"/{ctx.exam.slug}/{ctx.department.slug}/{s.slug}"}
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
