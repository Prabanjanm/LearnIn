from fastapi import APIRouter, Depends
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db
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


@router.get(
    "/",
    response_class=HTMLResponse
)
def home(request: Request, db: Session = Depends(get_db)):

    exams = exam_service.get_published(db)

    exam_cards = [
        {
            "title": exam.name,
            "url": f"/{exam.slug}",
            "meta": exam.code,
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
        }
        for mock_test in recent_mock_tests
    ]

    return templates.TemplateResponse(
        request=request,
        name="home/index.html",
        context={
            "exam_cards": exam_cards,
            "stats": stats,
            "paper_cards": paper_cards,
            "mock_test_cards": mock_test_cards,
        }
    )
