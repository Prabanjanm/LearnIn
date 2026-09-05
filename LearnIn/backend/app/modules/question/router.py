from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import StatusEnum
from app.modules.admin.dependencies import get_current_admin, get_optional_admin
from app.modules.admin.model import Admin

from .schema import (
    QuestionCheckRequest,
    QuestionCheckResponse,
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


# ---------------------------------------------------------------- public --
# Used by the practice page (paper/practice.html + static/js/practice.js):
# fetch a paper's published questions (answer key withheld) and check one
# answer at a time. Scoring always happens server-side.

@router.get("/", response_model=list[QuestionPublicResponse])
def get_published_by_paper(
    paper_id: int,
    db: Session = Depends(get_db),
):
    return question_service.get_published_by_paper(db, paper_id)


@router.post("/{question_id}/check", response_model=QuestionCheckResponse)
def check_answer(
    question_id: int,
    data: QuestionCheckRequest,
    db: Session = Depends(get_db),
):
    question = question_service.get_published_by_id(db, question_id)
    is_correct, _marks_awarded = question_service.evaluate_answer(question, data.answer)

    return QuestionCheckResponse(
        is_correct=bool(is_correct),
        correct_answer=question.correct_answer,
        explanation=question.explanation,
    )


@router.get("/{question_id}")
def get_one(
    question_id: int,
    db: Session = Depends(get_db),
    admin: Admin | None = Depends(get_optional_admin),
):
    """
    Admin gets the full record (correct_answer/explanation included) for
    any status - the CMS needs to review draft questions. Anyone else gets
    the same published-only, answer-withheld shape /check and the
    practice-page listing already use, and a 404 for a draft/archived
    question rather than leaking that it exists.
    """
    if admin is not None:
        question = question_service.get_or_404(db, question_id, "Question not found")
        return QuestionResponse.model_validate(question)

    question = question_service.get_published_by_id(db, question_id)
    return QuestionPublicResponse.model_validate(question)


# ----------------------------------------------------------------- admin --


@router.get("/{question_id}/admin", response_model=QuestionResponse)
def get_one_admin(
    question_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Explicit admin-only detail lookup (any status, full fields) - the
    CMS's own routes call this directly rather than relying on the
    optional-auth behavior of GET /{question_id} above."""
    return question_service.get_or_404(db, question_id, "Question not found")


@router.post("/", response_model=QuestionResponse)
def create(
    data: QuestionCreate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return question_service.create_question(db, data)


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
