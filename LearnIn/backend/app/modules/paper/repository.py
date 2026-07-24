from sqlalchemy.orm import Session, selectinload

from app.common.repositories.base_repository import BaseRepository
from app.core.enums import StatusEnum
from app.modules.department.model import Department
from app.modules.subject.model import Subject

from .model import Paper


class PaperRepository(BaseRepository):

    def __init__(self):
        super().__init__(Paper)

    def get_published_by_subject(
        self,
        db: Session,
        subject_id: int
    ):
        return (
            db.query(Paper)
            .filter(
                Paper.subject_id == subject_id,
                Paper.status == StatusEnum.PUBLISHED,
            )
            .order_by(Paper.year.desc())
            .all()
        )

    def get_published_by_id(
        self,
        db: Session,
        paper_id: int
    ):
        return (
            db.query(Paper)
            .filter(
                Paper.id == paper_id,
                Paper.status == StatusEnum.PUBLISHED,
            )
            .first()
        )

    def get_by_year(
        self,
        db: Session,
        subject_id: int,
        year: int
    ):
        """Unfiltered by status - used for the duplicate-year guard on create,
        which must catch a clash even against an existing DRAFT paper."""
        return (
            db.query(Paper)
            .filter(
                Paper.subject_id == subject_id,
                Paper.year == year,
            )
            .first()
        )

    def get_published_by_year(
        self,
        db: Session,
        subject_id: int,
        year: int
    ):
        return (
            db.query(Paper)
            .filter(
                Paper.subject_id == subject_id,
                Paper.year == year,
                Paper.status == StatusEnum.PUBLISHED,
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
            db.query(Paper)
            .options(
                selectinload(Paper.subject)
                .selectinload(Subject.department)
                .selectinload(Department.exam)
            )
            .filter(
                Paper.status == StatusEnum.PUBLISHED,
                Paper.title.ilike(pattern),
            )
            .limit(limit)
            .all()
        )
