import logging

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import AlreadyExistsException, GoogleDriveConfigError, InvalidCredentialsException
from app.common.rate_limit import rate_limit
from app.core.config import settings
from app.core.database import get_db
from app.core.google_drive import get_drive_client
from app.core.security import create_access_token, token_expire_minutes
from app.core.upload_policy import UploadValidationError, sanitize_filename, validate_upload

from .dependencies import INSTITUTION_ACCESS_TOKEN_COOKIE_NAME, get_current_institution_user, get_optional_institution_user
from .model import InstitutionUser
from .service import institution_user_service, request_institution_signup

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Institution Pages"])

templates = Jinja2Templates(directory="app/templates")


@router.get("/institution/login", response_class=HTMLResponse)
def login_page(user: InstitutionUser | None = Depends(get_optional_institution_user)):
    """
    Old direct link (email templates, institution/signup.html) - the
    Institution card now lives on /login itself (see account/login.html's
    flip-card picker), so this just lands the visitor there with that card
    already open instead of rendering its own separate page.
    """
    if user is not None:
        return RedirectResponse("/institution/dashboard", status_code=303)

    return RedirectResponse("/login?as=institution", status_code=307)


@router.post("/institution/login", response_class=HTMLResponse, dependencies=[Depends(rate_limit(10, 60))])
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        user = institution_user_service.authenticate(db, email, password)
    except InvalidCredentialsException as exc:
        return templates.TemplateResponse(
            request=request,
            name="account/login.html",
            context={"error": str(exc), "role": "institution"},
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
        max_age=token_expire_minutes("institution_user") * 60,
    )
    return response


@router.get("/institution/signup", response_class=HTMLResponse)
def signup_page(request: Request, user: InstitutionUser | None = Depends(get_optional_institution_user)):
    if user is not None:
        return RedirectResponse("/institution/dashboard", status_code=303)

    return templates.TemplateResponse(request=request, name="institution/signup.html", context={"error": None})


@router.post("/institution/signup", response_class=HTMLResponse, dependencies=[Depends(rate_limit(10, 60))])
def signup_submit(
    request: Request,
    institution_name: str = Form(...),
    contact_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        request_institution_signup(db, institution_name, contact_name, email, phone, password)
    except AlreadyExistsException as exc:
        return templates.TemplateResponse(
            request=request,
            name="institution/signup.html",
            context={"error": str(exc)},
            status_code=409,
        )

    return templates.TemplateResponse(
        request=request,
        name="institution/signup_pending.html",
        context={"institution_name": institution_name, "contact_name": contact_name},
    )


@router.get("/institution/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(INSTITUTION_ACCESS_TOKEN_COOKIE_NAME)
    return response


@router.get("/institution/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: InstitutionUser | None = Depends(get_optional_institution_user),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)

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


# --------------------------------------------------------- file uploads --

@router.post("/institution/upload")
async def upload_file(
    file: UploadFile = File(...),
    category: str | None = Form(None),
    _user: InstitutionUser = Depends(get_current_institution_user),
):
    """
    Institution-side equivalent of /admin/upload (app.modules.admin.pages)
    - same validation/Drive-upload path, just gated by an institution
    session instead of an admin one, for upload-widget.js's institution
    forms (e.g. the conducted-test paper upload).
    """
    content = await file.read()
    filename = sanitize_filename(file.filename or "upload")
    mime_type = file.content_type or "application/octet-stream"

    try:
        validate_upload(category, filename, mime_type, len(content), content)
    except UploadValidationError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    client = get_drive_client()

    try:
        result = client.upload_file(content, filename=filename, mime_type=mime_type, category=category)
    except GoogleDriveConfigError as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)
    except Exception:
        logger.exception("Google Drive upload failed for category=%s filename=%s", category, filename)
        return JSONResponse({"error": "File upload failed. Please try again."}, status_code=502)

    return {
        "file_id": result.file_id,
        "mime_type": result.mime_type,
        "file_size": result.file_size,
        "filename": result.name,
    }
