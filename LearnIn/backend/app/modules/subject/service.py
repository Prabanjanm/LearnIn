from sqlalchemy.orm import Session

from .repository import SubjectRepository


class SubjectService:

    @staticmethod
    def list(db: Session):

        return SubjectRepository.get_all(db)


    @staticmethod
    def details(db: Session, item_id: int):

        return SubjectRepository.get_by_id(
            db,
            item_id
        )
