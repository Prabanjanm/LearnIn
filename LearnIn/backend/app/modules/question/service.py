from sqlalchemy.orm import Session

from .repository import QuestionRepository


class QuestionService:

    @staticmethod
    def list(db: Session):

        return QuestionRepository.get_all(db)


    @staticmethod
    def details(db: Session, item_id: int):

        return QuestionRepository.get_by_id(
            db,
            item_id
        )
