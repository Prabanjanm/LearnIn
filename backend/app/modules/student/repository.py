from sqlalchemy.orm import Session

from app.common.repositories.base_repository import BaseRepository

from .model import Student


class StudentRepository(BaseRepository):

    def __init__(self):
        super().__init__(Student)

    def get_by_email(
        self,
        db: Session,
        email: str
    ):
        return (
            db.query(Student)
            .filter(Student.email == email)
            .first()
        )
