from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.student.dependencies import get_optional_student
from app.modules.student.model import Student

from .service import conducted_test_attempt_service

router = APIRouter(tags=["Conducted Tests (Student Pages)"])

templates = Jinja2Templates(directory="app/templates")


@router.get("/join-test", response_class=HTMLResponse)
def join_page(request: Request, student: Student | None = Depends(get_optional_student)):
    if student is None:
        return RedirectResponse("/login?next=/join-test", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="conducted_test/join.html",
        context={"student": student},
    )


@router.get("/conducted-tests/{conducted_test_id}", response_class=HTMLResponse)
def take_page(
    conducted_test_id: int,
    request: Request,
    db: Session = Depends(get_db),
    student: Student | None = Depends(get_optional_student),
):
    if student is None:
        return RedirectResponse(f"/login?next=/conducted-tests/{conducted_test_id}", status_code=303)

    from app.modules.conducted_test.service import conducted_test_service

    conducted_test = conducted_test_service.get_or_404(db, conducted_test_id, "Conducted test not found")

    return templates.TemplateResponse(
        request=request,
        name="conducted_test/take.html",
        context={"student": student, "conducted_test": conducted_test},
    )


@router.get("/conducted-tests/results/{result_code}", response_class=HTMLResponse)
def result_page(
    result_code: str,
    request: Request,
    db: Session = Depends(get_db),
    student: Student | None = Depends(get_optional_student),
):
    if student is None:
        return RedirectResponse(f"/login?next=/conducted-tests/results/{result_code}", status_code=303)

    report = conducted_test_attempt_service.get_result_for_student(db, result_code, student)

    return templates.TemplateResponse(
        request=request,
        name="conducted_test/report.html",
        context={"student": student, "report": report},
    )


@router.get("/profile/test-results", response_class=HTMLResponse)
def my_results_page(
    request: Request,
    db: Session = Depends(get_db),
    student: Student | None = Depends(get_optional_student),
):
    if student is None:
        return RedirectResponse("/login?next=/profile/test-results", status_code=303)

    attempts = conducted_test_attempt_service.get_my_results(db, student)

    return templates.TemplateResponse(
        request=request,
        name="conducted_test/my_results.html",
        context={"student": student, "attempts": attempts},
    )
