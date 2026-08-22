from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import StatusEnum
from app.modules.admin.dependencies import get_current_admin

from .schema import (
    AnswerCheck,
    AnswerCheckResult,
    QuestionCreate,
    QuestionPublicResponse,
    QuestionResponse,
    QuestionUpdate,
)
from .service import question_service

router = APIRouter(
    prefix="/api/questions",
    tags=["Questions"]
)


@router.get("/", response_model=list[QuestionPublicResponse])
def get_all(
    paper_id: int,
    db: Session = Depends(get_db)
):
    return question_service.get_published_by_paper(db, paper_id)


@router.get("/{question_id}", response_model=QuestionPublicResponse)
def get_one(
    question_id: int,
    db: Session = Depends(get_db)
):
    return question_service.get_published_by_id(db, question_id)


@router.post("/{question_id}/check", response_model=AnswerCheckResult)
def check_answer(
    question_id: int,
    data: AnswerCheck,
    db: Session = Depends(get_db)
):
    return question_service.check_answer(db, question_id, data.answer)


@router.post("/", response_model=QuestionResponse)
def create(
    data: QuestionCreate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return question_service.create_question(db, data)


@router.get("/{question_id}/admin", response_model=QuestionResponse)
def get_one_admin(
    question_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Admin view of a single question (any status, includes the answer)."""
    return question_service.get_or_404(db, question_id, "Question not found")


@router.patch("/{question_id}", response_model=QuestionResponse)
def update(
    question_id: int,
    data: QuestionUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    question = question_service.get_or_404(db, question_id, "Question not found")
    return question_service.update_question(db, question, data)


@router.post("/{question_id}/publish", response_model=QuestionResponse)
def publish(
    question_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    question = question_service.get_or_404(db, question_id, "Question not found")
    return question_service.update_question(db, question, QuestionUpdate(status=StatusEnum.PUBLISHED))


@router.post("/{question_id}/archive", response_model=QuestionResponse)
def archive(
    question_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    question = question_service.get_or_404(db, question_id, "Question not found")
    return question_service.update_question(db, question, QuestionUpdate(status=StatusEnum.ARCHIVED))


@router.delete("/{question_id}", status_code=204)
def delete(
    question_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    question = question_service.get_or_404(db, question_id, "Question not found")
    question_service.delete_question(db, question)
