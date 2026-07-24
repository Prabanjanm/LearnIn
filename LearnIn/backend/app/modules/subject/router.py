from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin.dependencies import get_current_admin

from .schema import SubjectCreate, SubjectResponse
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


@router.get("/{subject_id}", response_model=SubjectResponse)
def get_one(
    subject_id: int,
    db: Session = Depends(get_db)
):
    return subject_service.get_published_by_id(db, subject_id)


@router.post("/", response_model=SubjectResponse)
def create(
    data: SubjectCreate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return subject_service.create_subject(db, data)
