from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin.dependencies import get_current_admin

from .schema import (
    AnswerCheck,
    AnswerCheckResult,
    QuestionCreate,
    QuestionPublicResponse,
    QuestionResponse,
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
