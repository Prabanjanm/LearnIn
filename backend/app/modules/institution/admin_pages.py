from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin.dependencies import get_optional_admin
from app.modules.admin.model import Admin

from .service import institution_service

router = APIRouter(tags=["Institutions (Admin Pages)"])

templates = Jinja2Templates(directory="app/templates")


@router.get("/admin/institutions", response_class=HTMLResponse)
def list_page(request: Request, admin: Admin | None = Depends(get_optional_admin)):
    if admin is None:
        return RedirectResponse("/admin/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="institution/admin_list.html",
        context={"admin": admin},
    )


@router.get("/admin/institutions/new", response_class=HTMLResponse)
def new_page(request: Request, admin: Admin | None = Depends(get_optional_admin)):
    if admin is None:
        return RedirectResponse("/admin/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="institution/admin_form.html",
        context={"admin": admin},
    )


@router.get("/admin/institutions/{institution_id}", response_class=HTMLResponse)
def detail_page(
    institution_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: Admin | None = Depends(get_optional_admin),
):
    if admin is None:
        return RedirectResponse("/admin/login", status_code=303)

    institution = institution_service.get_or_404(db, institution_id, "Institution not found")

    return templates.TemplateResponse(
        request=request,
        name="institution/admin_detail.html",
        context={"admin": admin, "institution": institution},
    )
