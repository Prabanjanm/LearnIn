from sqlalchemy.orm import Session

from .repository import PaperRepository


class PaperService:

    @staticmethod
    def list(db: Session):

        return PaperRepository.get_all(db)


    @staticmethod
    def details(db: Session, item_id: int):

        return PaperRepository.get_by_id(
            db,
            item_id
        )
