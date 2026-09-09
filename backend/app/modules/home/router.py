from fastapi import APIRouter, Depends
from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.common.utils.category_illustration import resolve_category_illustration
from app.common.utils.drive_urls import drive_thumbnail_url
from app.core.database import get_db
from app.modules.blog.service import blog_service
from app.modules.exam.service import exam_service
from app.modules.mock_test.service import mock_test_service
from app.modules.paper.service import paper_service
from app.modules.question.service import question_service

router = APIRouter(
    tags=["Home"]
)

templates = Jinja2Templates(
    directory="app/templates"
)


@router.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Some browsers/crawlers request this conventional path directly,
    ignoring the <link rel="icon"> tags in <head> - serve the same
    generated favicon so that request doesn't fall through to the 404 page."""
    return FileResponse("app/static/img/brand/favicon.ico")


@router.get(
    "/",
    response_class=HTMLResponse
)
def home(request: Request, db: Session = Depends(get_db)):

    exams = exam_service.get_published(db)

    # Single grouped query each - never one query per exam - so real
    # per-exam paper/mock-test counts stay cheap regardless of how many
    # exams exist.
    paper_counts = paper_service.count_published_by_exam(db)
    mock_test_counts = mock_test_service.count_published_by_exam(db)

    exam_cards = [
        {
            "title": exam.name,
            "code": exam.code,
            "url": f"/{exam.slug}",
            "description": exam.description,
            "icon_url": drive_thumbnail_url(exam.icon_file_id) or resolve_category_illustration(exam.name),
            "paper_count": paper_counts.get(exam.id, 0),
            "mock_test_count": mock_test_counts.get(exam.id, 0),
        }
        for exam in exams
    ]

    stats = [
        {"value": len(exams), "label": "Exam Categories"},
        {"value": question_service.count_published(db), "label": "Questions"},
        {"value": paper_service.count_published(db), "label": "Previous Year Papers"},
        {"value": mock_test_service.count_published(db), "label": "Mock Tests"},
    ]

    # Homepage sections only ever pull a small, fixed number of the most
    # recent rows (see paper_service.get_recent_published /
    # mock_test_service.get_recent_published) - never the full table -
    # so the homepage stays fast regardless of how much content exists.
    recent_papers = paper_service.get_recent_published(db, limit=6)
    paper_cards = [
        {
            "title": f"{paper.subject.department.exam.code} {paper.year} - {paper.subject.name}",
            "url": f"/{paper.subject.department.exam.slug}/{paper.subject.department.slug}/{paper.subject.slug}/{paper.year}",
            "meta": f"{paper.total_questions} questions" + (" · Answer key available" if paper.answer_file_id else ""),
            "icon": "paper",
        }
        for paper in recent_papers
    ]

    recent_mock_tests = mock_test_service.get_recent_published(db, limit=6)
    mock_test_cards = [
        {
            "title": mock_test.title,
            "url": (
                f"/{mock_test.paper.subject.department.exam.slug}/{mock_test.paper.subject.department.slug}"
                f"/{mock_test.paper.subject.slug}/{mock_test.paper.year}/mock-test/{mock_test.id}"
            ),
            "meta": f"{mock_test.total_questions} questions · {mock_test.duration} min",
            "icon": "mock_test",
        }
        for mock_test in recent_mock_tests
    ]

    recent_blogs, _ = blog_service.get_published(db, page=1, page_size=3)
    blog_cards = [
        {
            "title": blog.title,
            "url": f"/blogs/{blog.slug}",
            "category": blog.category,
            "date": blog.published_date.strftime("%b %d, %Y") if blog.published_date else None,
            "image_url": drive_thumbnail_url(blog.thumbnail_file_id),
        }
        for blog in recent_blogs
    ]

    return templates.TemplateResponse(
        request=request,
        name="home/index.html",
        context={
            "exam_cards": exam_cards,
            "stats": stats,
            "paper_cards": paper_cards,
            "mock_test_cards": mock_test_cards,
            "blog_cards": blog_cards,
        }
    )
