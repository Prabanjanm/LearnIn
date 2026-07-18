from sqlalchemy.orm import Session

from .repository import NoteRepository


class NoteService:

    @staticmethod
    def list(db: Session):

        return NoteRepository.get_all(db)


    @staticmethod
    def details(db: Session, item_id: int):

        return NoteRepository.get_by_id(
            db,
            item_id
        )
