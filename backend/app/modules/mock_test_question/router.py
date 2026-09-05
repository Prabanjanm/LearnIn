from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin.dependencies import get_current_admin
from app.modules.mock_test.service import mock_test_service

from .schema import MockTestQuestionCreate, MockTestQuestionResponse
from .service import mock_test_question_service

router = APIRouter(
    prefix="/api/mock-test-questions",
    tags=["Mock Test Questions"]
)


@router.get("/", response_model=list[MockTestQuestionResponse])
def get_all(
    mock_test_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """
    Admin-only listing (any status). Public consumers must go through
    GET /api/mock-tests/{id}/questions, which enforces the parent mock
    test is PUBLISHED before returning anything.
    """
    return mock_test_question_service.get_by_mock_test(db, mock_test_id)


@router.post("/", response_model=MockTestQuestionResponse)
def add_question(
    data: MockTestQuestionCreate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    mock_test_service.get_or_404(db, data.mock_test_id, "Mock test not found")
    return mock_test_question_service.add_question(db, data)


@router.delete("/{link_id}", status_code=204)
def remove_question(
    link_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    link = mock_test_question_service.get_or_404(db, link_id, "Mock test question link not found")
    mock_test_question_service.remove_question(db, link)
