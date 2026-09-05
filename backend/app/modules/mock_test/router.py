from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.rate_limit import rate_limit
from app.core.database import get_db
from app.core.enums import StatusEnum
from app.modules.admin.dependencies import get_current_admin
from app.modules.mock_test_question.schema import MockTestQuestionReorder, MockTestQuestionResponse
from app.modules.mock_test_question.service import mock_test_question_service
from app.modules.student.dependencies import get_optional_student
from app.modules.student.model import Student

from .schema import (
    MockTestAnswerRequest,
    MockTestCreate,
    MockTestQuestionEntry,
    MockTestResponse,
    MockTestStartRequest,
    MockTestStartResponse,
    MockTestSubmitRequest,
    MockTestSubmitResponse,
    MockTestUpdate,
)
from .service import mock_test_service

router = APIRouter(
    prefix="/api/mock-tests",
    tags=["Mock Tests"]
)


@router.get("/", response_model=list[MockTestResponse])
def get_all(
    paper_id: int,
    db: Session = Depends(get_db)
):
    return mock_test_service.get_published_by_paper(db, paper_id)


@router.get("/{mock_test_id}", response_model=MockTestResponse)
def get_one(
    mock_test_id: int,
    db: Session = Depends(get_db)
):
    return mock_test_service.get_published_by_id(db, mock_test_id)


@router.get("/{mock_test_id}/questions", response_model=list[MockTestQuestionEntry])
def get_questions(
    mock_test_id: int,
    db: Session = Depends(get_db),
):
    questions = mock_test_service.get_questions_for_taking(db, mock_test_id)
    return [{"question": question} for question in questions]


@router.post("/{mock_test_id}/start", response_model=MockTestStartResponse)
def start(
    mock_test_id: int,
    data: MockTestStartRequest,
    db: Session = Depends(get_db),
    student: Student | None = Depends(get_optional_student),
):
    """
    Establishes the server-authoritative clock for this attempt (see
    mock_test_service.start_session). The frontend calls this once when
    "Start Test" is clicked, and again on every page load/refresh with the
    same client_token to recover the real deadline - the response is
    idempotent, so calling it twice never resets the timer.
    """
    return mock_test_service.start_session(
        db,
        mock_test_id,
        data.client_token,
        student.id if student else None,
    )


@router.post("/{mock_test_id}/answer", status_code=204, dependencies=[Depends(rate_limit(120, 60))])
def save_answer(
    mock_test_id: int,
    data: MockTestAnswerRequest,
    db: Session = Depends(get_db),
    student: Student | None = Depends(get_optional_student),
):
    """
    Persists one question's answer/mark within the active session
    identified by client_token (see mock_test_service.save_answer /
    MockTestSessionService.save_answer for the full validation chain:
    session ownership, not-submitted, not-expired, question belongs to
    this mock test, option belongs to this question). Called on every
    Save & Next / Mark for Review / Clear Answer so an active test is
    resumable from the server, not just from localStorage.
    """
    mock_test_service.save_answer(
        db,
        mock_test_id,
        data.client_token,
        student.id if student else None,
        data.question_id,
        data.answer,
        data.marked,
    )


@router.post("/{mock_test_id}/submit", response_model=MockTestSubmitResponse, dependencies=[Depends(rate_limit(20, 60))])
def submit(
    mock_test_id: int,
    data: MockTestSubmitRequest,
    db: Session = Depends(get_db),
    student: Student | None = Depends(get_optional_student),
):
    return mock_test_service.submit_attempt(
        db,
        mock_test_id,
        data.answers,
        student.id if student else None,
        data.client_token,
    )


@router.post("/", response_model=MockTestResponse)
def create(
    data: MockTestCreate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return mock_test_service.create_mock_test(db, data)


@router.put("/{mock_test_id}/questions/reorder", response_model=list[MockTestQuestionResponse])
def reorder_questions(
    mock_test_id: int,
    data: MockTestQuestionReorder,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    mock_test_service.get_or_404(db, mock_test_id, "Mock test not found")
    return mock_test_question_service.reorder(db, mock_test_id, data)


@router.patch("/{mock_test_id}", response_model=MockTestResponse)
def update(
    mock_test_id: int,
    data: MockTestUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    mock_test = mock_test_service.get_or_404(db, mock_test_id, "Mock test not found")
    return mock_test_service.update_mock_test(db, mock_test, data)


@router.post("/{mock_test_id}/publish", response_model=MockTestResponse)
def publish(
    mock_test_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    mock_test = mock_test_service.get_or_404(db, mock_test_id, "Mock test not found")
    return mock_test_service.update_mock_test(db, mock_test, MockTestUpdate(status=StatusEnum.PUBLISHED))


@router.post("/{mock_test_id}/archive", response_model=MockTestResponse)
def archive(
    mock_test_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    mock_test = mock_test_service.get_or_404(db, mock_test_id, "Mock test not found")
    return mock_test_service.update_mock_test(db, mock_test, MockTestUpdate(status=StatusEnum.ARCHIVED))


@router.delete("/{mock_test_id}", status_code=204)
def delete(
    mock_test_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    mock_test = mock_test_service.get_or_404(db, mock_test_id, "Mock test not found")
    mock_test_service.delete_mock_test(db, mock_test)
