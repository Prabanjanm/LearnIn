from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db

from .schema import ExamCreate
from .service import exam_service

router = APIRouter(
    prefix="/api/exams",
    tags=["Exams"]
)


@router.get("/")
def get_all(
    db: Session = Depends(get_db)
):
    return exam_service.get_all(db)


@router.get("/{exam_id}")
def get_one(
    exam_id: int,
    db: Session = Depends(get_db)
):
    return exam_service.get_by_id(
        db,
        exam_id
    )


@router.post("/")
def create(
    data: ExamCreate,
    db: Session = Depends(get_db)
):
    return exam_service.create_exam(
        db,
        data
    )