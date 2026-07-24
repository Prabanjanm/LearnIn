from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin.dependencies import get_current_admin

from .schema import ExamCreate, ExamResponse
from .service import exam_service

router = APIRouter(
    prefix="/api/exams",
    tags=["Exams"]
)


@router.get("/", response_model=list[ExamResponse])
def get_all(
    db: Session = Depends(get_db)
):
    return exam_service.get_published(db)


@router.get("/{exam_id}", response_model=ExamResponse)
def get_one(
    exam_id: int,
    db: Session = Depends(get_db)
):
    return exam_service.get_published_by_id(
        db,
        exam_id
    )


@router.post("/", response_model=ExamResponse)
def create(
    data: ExamCreate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return exam_service.create_exam(
        db,
        data
    )