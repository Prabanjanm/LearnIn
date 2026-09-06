from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import InvalidCredentialsException
from app.common.rate_limit import rate_limit
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token

from .dependencies import INSTITUTION_ACCESS_TOKEN_COOKIE_NAME, get_optional_institution_user
from .model import InstitutionUser
from .service import institution_user_service

router = APIRouter(tags=["Institution Pages"])

templates = Jinja2Templates(directory="app/templates")


@router.get("/institution/login", response_class=HTMLResponse)
def login_page(request: Request, user: InstitutionUser | None = Depends(get_optional_institution_user)):
    if user is not None:
        return RedirectResponse("/institution/dashboard", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="institution/login.html",
        context={"error": None},
    )


@router.post("/institution/login", dependencies=[Depends(rate_limit(10, 60))])
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        user = institution_user_service.authenticate(db, email, password)
    except InvalidCredentialsException:
        return templates.TemplateResponse(
            request=request,
            name="institution/login.html",
            context={"error": "Invalid email or password"},
            status_code=401,
        )

    token = create_access_token(
        subject=str(user.id),
        token_type="institution_user",
        token_version=user.token_version,
    )

    response = RedirectResponse("/institution/dashboard", status_code=303)
    response.set_cookie(
        key=INSTITUTION_ACCESS_TOKEN_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=not settings.DEBUG,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return response


@router.get("/institution/logout")
def logout():
    response = RedirectResponse("/institution/login", status_code=303)
    response.delete_cookie(INSTITUTION_ACCESS_TOKEN_COOKIE_NAME)
    return response


@router.get("/institution/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: InstitutionUser | None = Depends(get_optional_institution_user),
):
    if user is None:
        return RedirectResponse("/institution/login", status_code=303)

    from app.modules.conducted_test.repository import ConductedTestRepository
    from app.core.enums import StatusEnum

    tests = ConductedTestRepository().get_by_institution(db, user.institution_id)
    stats = {
        "total": len(tests),
        "active": sum(1 for t in tests if t.status == StatusEnum.PUBLISHED),
        "draft": sum(1 for t in tests if t.status == StatusEnum.DRAFT),
    }

    return templates.TemplateResponse(
        request=request,
        name="institution/dashboard.html",
        context={"user": user, "stats": stats},
    )
