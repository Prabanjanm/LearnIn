from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db

from .schema import MockTestQuestionResponse
from .service import mock_test_question_service

router = APIRouter(
    prefix="/api/mock-test-questions",
    tags=["Mock Test Questions"]
)


@router.get("/", response_model=list[MockTestQuestionResponse])
def get_all(
    mock_test_id: int,
    db: Session = Depends(get_db)
):
    return mock_test_question_service.get_by_mock_test(db, mock_test_id)
