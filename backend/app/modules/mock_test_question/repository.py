import uuid
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.common.repositories.base_repository import BaseRepository
from app.modules.question.model import Question

from .model import MockTestQuestion


class MockTestQuestionRepository(BaseRepository):

    def __init__(self):
        super().__init__(MockTestQuestion)

    def get_by_mock_test(
        self,
        db: Session,
        mock_test_id: uuid.UUID
    ):
        return (
            db.query(MockTestQuestion)
            .options(selectinload(MockTestQuestion.question).selectinload(Question.options))
            .filter(MockTestQuestion.mock_test_id == mock_test_id)
            .order_by(MockTestQuestion.question_order)
            .all()
        )

    def exists_link(
        self,
        db: Session,
        mock_test_id: uuid.UUID,
        question_id: uuid.UUID
    ) -> bool:
        return (
            db.query(MockTestQuestion)
            .filter(
                MockTestQuestion.mock_test_id == mock_test_id,
                MockTestQuestion.question_id == question_id,
            )
            .first()
            is not None
        )

    def get_max_order(
        self,
        db: Session,
        mock_test_id: uuid.UUID
    ) -> int:
        return (
            db.query(func.max(MockTestQuestion.question_order))
            .filter(MockTestQuestion.mock_test_id == mock_test_id)
            .scalar()
        ) or 0
