from sqlalchemy.orm import Session

from .repository import MockTestRepository


class MockTestService:

    @staticmethod
    def list(db: Session):

        return MockTestRepository.get_all(db)


    @staticmethod
    def details(db: Session, item_id: int):

        return MockTestRepository.get_by_id(
            db,
            item_id
        )
