from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import StatusEnum
from app.modules.admin.dependencies import get_current_admin
from app.modules.mock_test_question.schema import (
    MockTestQuestionReorder,
    MockTestQuestionResponse,
)
from app.modules.mock_test_question.service import mock_test_question_service

from .schema import (
    MockTestCreate,
    MockTestResponse,
    MockTestResult,
    MockTestSubmission,
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


@router.get("/{mock_test_id}/admin/questions", response_model=list[MockTestQuestionResponse])
def get_questions_admin(
    mock_test_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Admin view of a mock test's questions regardless of status."""
    mock_test_service.get_or_404(db, mock_test_id, "Mock test not found")
    return mock_test_question_service.get_by_mock_test(db, mock_test_id)


@router.put("/{mock_test_id}/questions/reorder", response_model=list[MockTestQuestionResponse])
def reorder_questions(
    mock_test_id: int,
    data: MockTestQuestionReorder,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    mock_test_service.get_or_404(db, mock_test_id, "Mock test not found")
    return mock_test_question_service.reorder(db, mock_test_id, data)
