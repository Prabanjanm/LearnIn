from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import NotFoundException
from app.core.database import get_db
from app.modules.admin.dependencies import get_current_admin
from app.modules.admin.model import Admin

from .schema import (
    InstitutionCreate,
    InstitutionResponse,
    InstitutionUpdate,
    InstitutionUserCreate,
    InstitutionUserResponse,
)
from .service import institution_service, institution_user_service

router = APIRouter(
    prefix="/api/admin/institutions",
    tags=["Institutions (Admin)"]
)

"""
LearnIn Admin's authority over Conducted Tests stops here: creating/
managing an Institution, creating its login accounts, and flipping its
conducted_test_enabled flag. Admin never creates or manages a
ConductedTest itself - see conducted_test/router.py, which is now
institution-only.
"""


@router.post("/", response_model=InstitutionResponse)
def create_institution(
    data: InstitutionCreate,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    return institution_service.create_institution(db, data)


@router.get("/", response_model=list[InstitutionResponse])
def list_institutions(
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    return institution_service.get_all(db)


@router.get("/{institution_id}", response_model=InstitutionResponse)
def get_institution(
    institution_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    return institution_service.get_or_404(db, institution_id, "Institution not found")


@router.patch("/{institution_id}", response_model=InstitutionResponse)
def update_institution(
    institution_id: int,
    data: InstitutionUpdate,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    institution = institution_service.get_or_404(db, institution_id, "Institution not found")
    return institution_service.update_institution(db, institution, data)


@router.post("/{institution_id}/conducted-test-feature")
def set_conducted_test_feature(
    institution_id: int,
    enabled: bool,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    """The one server-side switch that grants/revokes the whole Conducted
    Test feature for this tenant - enforced in conducted_test/service.py,
    not merely reflected in a UI toggle."""
    institution = institution_service.get_or_404(db, institution_id, "Institution not found")
    return InstitutionResponse.model_validate(
        institution_service.set_conducted_test_enabled(db, institution, enabled)
    )


@router.post("/{institution_id}/archive", response_model=InstitutionResponse)
def archive_institution(
    institution_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    institution = institution_service.get_or_404(db, institution_id, "Institution not found")
    return institution_service.archive(db, institution)


@router.post("/{institution_id}/activate", response_model=InstitutionResponse)
def activate_institution(
    institution_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    institution = institution_service.get_or_404(db, institution_id, "Institution not found")
    return institution_service.activate(db, institution)


@router.get("/{institution_id}/users", response_model=list[InstitutionUserResponse])
def list_institution_users(
    institution_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    institution_service.get_or_404(db, institution_id, "Institution not found")
    return institution_user_service.repository.get_by_institution(db, institution_id)


@router.post("/{institution_id}/users", response_model=InstitutionUserResponse)
def create_institution_user(
    institution_id: int,
    data: InstitutionUserCreate,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    institution_service.get_or_404(db, institution_id, "Institution not found")
    return institution_user_service.create_institution_user(
        db, institution_id, data.email, data.password, data.full_name
    )


@router.post("/{institution_id}/users/{user_id}/deactivate", response_model=InstitutionUserResponse)
def deactivate_institution_user(
    institution_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    institution_service.get_or_404(db, institution_id, "Institution not found")
    user = institution_user_service.get_or_404(db, user_id, "Institution user not found")
    if user.institution_id != institution_id:
        raise NotFoundException("Institution user not found")
    return institution_user_service.deactivate(db, user)
