from sqlalchemy.orm import Session

from .model import MockTest


class MockTestRepository:

    @staticmethod
    def get_all(db: Session):

        return db.query(MockTest).all()


    @staticmethod
    def get_by_id(db: Session, item_id: int):

        return db.query(MockTest).filter(
            MockTest.id == item_id
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
