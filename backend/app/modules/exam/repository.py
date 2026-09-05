from sqlalchemy.orm import Session

from app.common.repositories.base_repository import BaseRepository
from app.core.enums import StatusEnum

from .model import Exam


class ExamRepository(BaseRepository):

    def __init__(self):
        super().__init__(Exam)

    def get_published(
        self,
        db: Session
    ):
        return (
            db.query(Exam)
            .filter(Exam.status == StatusEnum.PUBLISHED)
            .order_by(Exam.display_order.asc(), Exam.name.asc())
            .all()
        )

    def get_published_by_id(
        self,
        db: Session,
        exam_id: int
    ):
        return (
            db.query(Exam)
            .filter(
                Exam.id == exam_id,
                Exam.status == StatusEnum.PUBLISHED,
            )
            .first()
        )

    def get_published_by_slug(
        self,
        db: Session,
        slug: str
    ):
        return (
            db.query(Exam)
            .filter(
                Exam.slug == slug,
                Exam.status == StatusEnum.PUBLISHED,
            )
            .first()
        )

    def search(
        self,
        db: Session,
        term: str,
        limit: int = 5
    ):
        pattern = f"%{term}%"
        return (
            db.query(Exam)
            .filter(
                Exam.status == StatusEnum.PUBLISHED,
                Exam.name.ilike(pattern),
            )
            .limit(limit)
            .all()
        )
