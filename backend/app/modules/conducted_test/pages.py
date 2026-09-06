from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.institution.dependencies import get_optional_institution_user
from app.modules.institution.model import InstitutionUser

from .service import conducted_test_service

router = APIRouter(tags=["Conducted Tests (Institution Pages)"])

templates = Jinja2Templates(directory="app/templates")


@router.get("/institution/conducted-tests", response_class=HTMLResponse)
def list_page(request: Request, user: InstitutionUser | None = Depends(get_optional_institution_user)):
    if user is None:
        return RedirectResponse("/institution/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="conducted_test/institution_list.html",
        context={"user": user},
    )


@router.get("/institution/conducted-tests/new", response_class=HTMLResponse)
def new_page(request: Request, user: InstitutionUser | None = Depends(get_optional_institution_user)):
    if user is None:
        return RedirectResponse("/institution/login", status_code=303)
    if not user.institution.conducted_test_enabled:
        return RedirectResponse("/institution/conducted-tests", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="conducted_test/institution_form.html",
        context={"user": user},
    )


@router.get("/institution/conducted-tests/{conducted_test_id}", response_class=HTMLResponse)
def detail_page(
    conducted_test_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: InstitutionUser | None = Depends(get_optional_institution_user),
):
    if user is None:
        return RedirectResponse("/institution/login", status_code=303)

    conducted_test = conducted_test_service.get_for_manage(db, conducted_test_id, user)

    return templates.TemplateResponse(
        request=request,
        name="conducted_test/institution_detail.html",
        context={"user": user, "conducted_test": conducted_test},
    )


@router.get("/institution/conducted-tests/{conducted_test_id}/results/{result_code}", response_class=HTMLResponse)
def institution_result_page(
    conducted_test_id: int,
    result_code: str,
    request: Request,
    db: Session = Depends(get_db),
    user: InstitutionUser | None = Depends(get_optional_institution_user),
):
    if user is None:
        return RedirectResponse("/institution/login", status_code=303)

    from app.modules.conducted_test_attempt.service import conducted_test_attempt_service

    conducted_test_service.get_for_manage(db, conducted_test_id, user)
    report = conducted_test_attempt_service.get_result_for_institution(db, result_code, user.institution_id)

    return templates.TemplateResponse(
        request=request,
        name="conducted_test/institution_report.html",
        context={"user": user, "report": report, "conducted_test_id": conducted_test_id},
    )
