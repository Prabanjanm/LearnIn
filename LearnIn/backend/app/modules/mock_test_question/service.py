from sqlalchemy.orm import Session

from app.common.services.base_service import BaseService

from .model import MockTestQuestion
from .repository import MockTestQuestionRepository


class MockTestQuestionService(BaseService):

    def __init__(self):
        super().__init__(MockTestQuestionRepository())

    def get_by_mock_test(
        self,
        db: Session,
        mock_test_id: int
    ):
        return self.repository.get_by_mock_test(db, mock_test_id)


mock_test_question_service = MockTestQuestionService()
