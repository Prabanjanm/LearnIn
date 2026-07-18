from sqlalchemy.orm import Session

from .repository import BlogRepository


class BlogService:

    @staticmethod
    def list(db: Session):

        return BlogRepository.get_all(db)


    @staticmethod
    def details(db: Session, item_id: int):

        return BlogRepository.get_by_id(
            db,
            item_id
        )
