from sqlalchemy.orm import Session

from .model import Download


class DownloadRepository:

    @staticmethod
    def get_all(db: Session):

        return db.query(Download).all()


    @staticmethod
    def get_by_id(db: Session, item_id: int):

        return db.query(Download).filter(
            Download.id == item_id
        ).first()


    @staticmethod
    def create(db: Session, obj):

        db.add(obj)

        db.commit()

        db.refresh(obj)

        return obj


    @staticmethod
    def delete(db: Session, obj):

        db.delete(obj)

        db.commit()
