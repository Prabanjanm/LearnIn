"""
Small JSON endpoints behind the institution's paper review screen -
mirrors paper_processing/router.py's shape, scoped to
get_current_institution_user instead of get_current_admin, and every
call is institution-scoped via institution_user.institution_id (never
just the {job_id} in the URL - see service.py).
"""
import uuid

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.institution.dependencies import get_current_institution_user
from app.modules.institution.model import InstitutionUser

from .schema import (
    ConductedTestPaperJobStatusResponse,
    ExtractedQuestionIn,
    ExtractedQuestionResponse,
)
from .service import conducted_test_paper_job_service

router = APIRouter(
    prefix="/api/institution/conducted-test-papers",
    tags=["Conducted Test Papers (Institution)"],
)


@router.get("/{job_id}/status", response_model=ConductedTestPaperJobStatusResponse)
def job_status(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    institution_user: InstitutionUser = Depends(get_current_institution_user),
):
    return conducted_test_paper_job_service.get_job(db, job_id, institution_user.institution_id)


@router.get("/{job_id}/questions", response_model=list[ExtractedQuestionResponse])
def list_questions(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    institution_user: InstitutionUser = Depends(get_current_institution_user),
):
    conducted_test_paper_job_service.get_job(db, job_id, institution_user.institution_id)
    return conducted_test_paper_job_service.list_questions(db, job_id)


@router.post("/{job_id}/questions", response_model=ExtractedQuestionResponse)
def add_question(
    job_id: uuid.UUID,
    data: ExtractedQuestionIn,
    db: Session = Depends(get_db),
    institution_user: InstitutionUser = Depends(get_current_institution_user),
):
    return conducted_test_paper_job_service.add_question(db, job_id, institution_user.institution_id, data)


@router.put("/{job_id}/questions/{question_id}", response_model=ExtractedQuestionResponse)
def update_question(
    job_id: uuid.UUID,
    question_id: uuid.UUID,
    data: ExtractedQuestionIn,
    db: Session = Depends(get_db),
    institution_user: InstitutionUser = Depends(get_current_institution_user),
):
    return conducted_test_paper_job_service.update_question(
        db, job_id, institution_user.institution_id, question_id, data
    )


@router.delete("/{job_id}/questions/{question_id}")
def delete_question(
    job_id: uuid.UUID,
    question_id: uuid.UUID,
    db: Session = Depends(get_db),
    institution_user: InstitutionUser = Depends(get_current_institution_user),
):
    conducted_test_paper_job_service.delete_question(db, job_id, institution_user.institution_id, question_id)
    return {"deleted": True}


@router.post("/{job_id}/questions/{question_id}/move")
def move_question(
    job_id: uuid.UUID,
    question_id: uuid.UUID,
    direction: str = Body(embed=True),
    db: Session = Depends(get_db),
    institution_user: InstitutionUser = Depends(get_current_institution_user),
):
    conducted_test_paper_job_service.move_question(
        db, job_id, institution_user.institution_id, question_id, direction
    )
    return {"moved": True}


@router.post("/{job_id}/questions/{question_id}/needs-review", response_model=ExtractedQuestionResponse)
def set_needs_review(
    job_id: uuid.UUID,
    question_id: uuid.UUID,
    needs_review: bool = Body(embed=True),
    db: Session = Depends(get_db),
    institution_user: InstitutionUser = Depends(get_current_institution_user),
):
    return conducted_test_paper_job_service.set_needs_review(
        db, job_id, institution_user.institution_id, question_id, needs_review
    )
