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
