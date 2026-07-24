from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin.dependencies import get_current_admin
from app.modules.mock_test_question.schema import MockTestQuestionResponse
from app.modules.mock_test_question.service import mock_test_question_service

from .schema import (
    MockTestCreate,
    MockTestResponse,
    MockTestResult,
    MockTestSubmission,
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


@router.get("/{mock_test_id}/questions", response_model=list[MockTestQuestionResponse])
def get_questions(
    mock_test_id: int,
    db: Session = Depends(get_db)
):
    # Raises NotFoundException (-> 404) if the mock test doesn't exist or isn't
    # published yet - a draft test's questions must not be reachable directly.
    mock_test_service.get_published_by_id(db, mock_test_id)

    return mock_test_question_service.get_by_mock_test(db, mock_test_id)


@router.post("/{mock_test_id}/submit", response_model=MockTestResult)
def submit(
    mock_test_id: int,
    submission: MockTestSubmission,
    db: Session = Depends(get_db)
):
    return mock_test_service.submit_attempt(db, mock_test_id, submission)


@router.post("/", response_model=MockTestResponse)
def create(
    data: MockTestCreate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return mock_test_service.create_mock_test(db, data)
