from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin.dependencies import get_current_admin

from .schema import SubjectCreate, SubjectResponse, SubjectUpdate
from .service import subject_service

router = APIRouter(
    prefix="/api/subjects",
    tags=["Subjects"]
)


@router.get("/", response_model=list[SubjectResponse])
def get_all(
    department_id: int,
    db: Session = Depends(get_db)
):
    return subject_service.get_published_by_department(db, department_id)


@router.get("/{department_id}/{slug}", response_model=SubjectResponse)
def get_one(
    department_id: int,
    slug: str,
    db: Session = Depends(get_db)
):
    return subject_service.get_published_by_slug(db, department_id, slug)


@router.post("/", response_model=SubjectResponse)
def create(
    data: SubjectCreate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return subject_service.create_subject(db, data)


@router.patch("/{subject_id}", response_model=SubjectResponse)
def update(
    subject_id: int,
    data: SubjectUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    subject = subject_service.get_or_404(db, subject_id, "Subject not found")
    return subject_service.update_subject(db, subject, data)


@router.delete("/{subject_id}", status_code=204)
def delete(
    subject_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    subject = subject_service.get_or_404(db, subject_id, "Subject not found")
    subject_service.delete_subject(db, subject)
