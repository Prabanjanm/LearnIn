from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.common.repositories.base_repository import BaseRepository

from .model import MockTestQuestion


class MockTestQuestionRepository(BaseRepository):

    def __init__(self):
        super().__init__(MockTestQuestion)

    def get_by_mock_test(
        self,
        db: Session,
        mock_test_id: int
    ):
        return (
            db.query(MockTestQuestion)
            .options(selectinload(MockTestQuestion.question))
            .filter(MockTestQuestion.mock_test_id == mock_test_id)
            .order_by(MockTestQuestion.question_order)
            .all()
        )

    def exists_link(
        self,
        db: Session,
        mock_test_id: int,
        question_id: int
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
        mock_test_id: int
    ) -> int:
        return (
            db.query(func.max(MockTestQuestion.question_order))
            .filter(MockTestQuestion.mock_test_id == mock_test_id)
            .scalar()
        ) or 0
