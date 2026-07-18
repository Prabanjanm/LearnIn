from sqlalchemy.orm import Session

from app.common.repositories.base_repository import BaseRepository
from .model import Exam


class ExamRepository(BaseRepository):

    def __init__(self):
        super().__init__(Exam)

    def get_by_slug(
        self,
        db: Session,
        slug: str
    ):
        return (
            db.query(Exam)
            .filter(Exam.slug == slug)
            .first()
        )

    def exists_by_code(
        self,
        db: Session,
        code: str
    ):
        return (
            db.query(Exam)
            .filter(Exam.code == code)
            .first()
        )