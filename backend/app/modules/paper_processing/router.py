"""
Small JSON endpoints behind the review screen.

Each one does a single focused mutation and returns the updated row (or the
job's counters), so the vanilla-JS review page can update in place without a
full form round-trip. Every route requires an authenticated admin.
"""
from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin.dependencies import get_current_admin
from app.modules.admin.model import Admin

from .schema import (
    ExtractedQuestionImageAttach,
    ExtractedQuestionImageResponse,
    ExtractedQuestionIn,
    ExtractedQuestionResponse,
    PaperProcessingJobStatusResponse,
    ReassignImageRequest,
    SplitRequest,
)
from .service import paper_processing_service

router = APIRouter(
    prefix="/api/admin/paper-processing",
    tags=["Paper Processing"],
)


@router.get("/{job_id}/status", response_model=PaperProcessingJobStatusResponse)
def job_status(
    job_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    """Polled by the status page until the pipeline reaches a terminal state."""
    return paper_processing_service.get_job(db, job_id)


@router.get("/{job_id}/questions", response_model=list[ExtractedQuestionResponse])
def list_questions(
    job_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    paper_processing_service.get_job(db, job_id)
    return paper_processing_service.list_questions(db, job_id)


@router.post("/{job_id}/questions", response_model=ExtractedQuestionResponse)
def add_question(
    job_id: int,
    data: ExtractedQuestionIn,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    return paper_processing_service.add_question(db, job_id, data)


@router.put("/{job_id}/questions/{question_id}", response_model=ExtractedQuestionResponse)
def update_question(
    job_id: int,
    question_id: int,
    data: ExtractedQuestionIn,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    return paper_processing_service.update_question(db, job_id, question_id, data)


@router.delete("/{job_id}/questions/{question_id}")
def delete_question(
    job_id: int,
    question_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    paper_processing_service.delete_question(db, job_id, question_id)
    return {"deleted": True}


@router.post("/{job_id}/questions/{question_id}/move")
def move_question(
    job_id: int,
    question_id: int,
    direction: str = Body(embed=True),
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    paper_processing_service.move_question(db, job_id, question_id, direction)
    return {"moved": True}


@router.post("/{job_id}/questions/{question_id}/needs-review", response_model=ExtractedQuestionResponse)
def set_needs_review(
    job_id: int,
    question_id: int,
    needs_review: bool = Body(embed=True),
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    return paper_processing_service.set_needs_review(db, job_id, question_id, needs_review)


@router.post("/{job_id}/questions/{question_id}/split", response_model=list[ExtractedQuestionResponse])
def split_question(
    job_id: int,
    question_id: int,
    data: SplitRequest | None = None,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    return paper_processing_service.split_question(
        db, job_id, question_id, data.split_at if data else None
    )


@router.post("/{job_id}/questions/{question_id}/merge", response_model=ExtractedQuestionResponse)
def merge_question(
    job_id: int,
    question_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    return paper_processing_service.merge_with_next(db, job_id, question_id)


# ------------------------------------------------------ question images --
# The admin's own corrections on top of whatever the pipeline detected
# automatically - attach one it missed, replace/remove a wrong one, or move
# one to the question it actually belongs to. Uploads go through the
# existing /admin/upload endpoint first (category "question_images"); these
# routes only ever receive the resulting {file_id, mime_type, file_size,
# filename}, never raw file bytes.

@router.post(
    "/{job_id}/questions/{question_id}/images",
    response_model=ExtractedQuestionImageResponse,
)
def add_question_image(
    job_id: int,
    question_id: int,
    data: ExtractedQuestionImageAttach,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    return paper_processing_service.add_manual_image(
        db, job_id, question_id,
        data.file_id, data.mime_type, data.file_size, data.filename,
    )


@router.put(
    "/{job_id}/questions/{question_id}/images/{image_id}",
    response_model=ExtractedQuestionImageResponse,
)
def replace_question_image(
    job_id: int,
    question_id: int,
    image_id: int,
    data: ExtractedQuestionImageAttach,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    return paper_processing_service.replace_image(
        db, job_id, question_id, image_id,
        data.file_id, data.mime_type, data.file_size, data.filename,
    )


@router.delete("/{job_id}/questions/{question_id}/images/{image_id}")
def delete_question_image(
    job_id: int,
    question_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    paper_processing_service.remove_image(db, job_id, question_id, image_id)
    return {"deleted": True}


@router.post(
    "/{job_id}/questions/{question_id}/images/{image_id}/reassign",
    response_model=ExtractedQuestionImageResponse,
)
def reassign_question_image(
    job_id: int,
    question_id: int,
    image_id: int,
    data: ReassignImageRequest,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    return paper_processing_service.reassign_image(
        db, job_id, question_id, image_id, data.target_question_id,
    )


@router.post("/{job_id}/questions/{question_id}/images/{image_id}/move")
def move_question_image(
    job_id: int,
    question_id: int,
    image_id: int,
    direction: str = Body(embed=True),
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    paper_processing_service.move_image(db, job_id, question_id, image_id, direction)
    return {"moved": True}
