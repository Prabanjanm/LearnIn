from sqlalchemy.orm import Session

from app.common.repositories.base_repository import BaseRepository
from app.core.enums import StatusEnum

from .model import MockTest


class MockTestRepository(BaseRepository):

    def __init__(self):
        super().__init__(MockTest)

    def get_published_by_paper(
        self,
        db: Session,
        paper_id: int
    ):
        return (
            db.query(MockTest)
            .filter(
                MockTest.paper_id == paper_id,
                MockTest.status == StatusEnum.PUBLISHED,
            )
            .all()
        )

    def get_published_by_id(
        self,
        db: Session,
        mock_test_id: int
    ):
        return (
            db.query(MockTest)
            .filter(
                MockTest.id == mock_test_id,
                MockTest.status == StatusEnum.PUBLISHED,
            )
            .first()
        )
