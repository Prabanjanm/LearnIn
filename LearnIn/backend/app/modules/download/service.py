from sqlalchemy.orm import Session

from .repository import DownloadRepository


class DownloadService:

    @staticmethod
    def list(db: Session):

        return DownloadRepository.get_all(db)


    @staticmethod
    def details(db: Session, item_id: int):

        return DownloadRepository.get_by_id(
            db,
            item_id
        )
