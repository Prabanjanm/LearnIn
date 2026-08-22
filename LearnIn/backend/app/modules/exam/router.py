from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import StatusEnum
from app.modules.admin.dependencies import get_current_admin

from .schema import ExamCreate, ExamResponse, ExamUpdate
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


@router.patch("/{exam_id}", response_model=ExamResponse)
def update(
    exam_id: int,
    data: ExamUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    exam = exam_service.get_or_404(db, exam_id, "Exam not found")
    return exam_service.update_exam(db, exam, data)


@router.post("/{exam_id}/publish", response_model=ExamResponse)
def publish(
    exam_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    exam = exam_service.get_or_404(db, exam_id, "Exam not found")
    return exam_service.update_exam(db, exam, ExamUpdate(status=StatusEnum.PUBLISHED))


@router.post("/{exam_id}/archive", response_model=ExamResponse)
def archive(
    exam_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    exam = exam_service.get_or_404(db, exam_id, "Exam not found")
    return exam_service.update_exam(db, exam, ExamUpdate(status=StatusEnum.ARCHIVED))


@router.delete("/{exam_id}", status_code=204)
def delete(
    exam_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    exam = exam_service.get_or_404(db, exam_id, "Exam not found")
    exam_service.delete_exam(db, exam)