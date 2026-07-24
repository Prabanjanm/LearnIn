from sqlalchemy.orm import Session, selectinload

from app.common.repositories.base_repository import BaseRepository
from app.core.enums import StatusEnum
from app.modules.department.model import Department

from .model import Subject


class SubjectRepository(BaseRepository):

    def __init__(self):
        super().__init__(Subject)

    def get_published_by_department(
        self,
        db: Session,
        department_id: int
    ):
        return (
            db.query(Subject)
            .filter(
                Subject.department_id == department_id,
                Subject.status == StatusEnum.PUBLISHED,
            )
            .order_by(Subject.display_order)
            .all()
        )

    def get_published_by_slug(
        self,
        db: Session,
        department_id: int,
        slug: str
    ):
        return (
            db.query(Subject)
            .filter(
                Subject.department_id == department_id,
                Subject.slug == slug,
                Subject.status == StatusEnum.PUBLISHED,
            )
            .first()
        )

    def get_published_by_id(
        self,
        db: Session,
        subject_id: int
    ):
        return (
            db.query(Subject)
            .filter(
                Subject.id == subject_id,
                Subject.status == StatusEnum.PUBLISHED,
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
            db.query(Subject)
            .options(
                selectinload(Subject.department).selectinload(Department.exam)
            )
            .filter(
                Subject.status == StatusEnum.PUBLISHED,
                Subject.name.ilike(pattern),
            )
            .limit(limit)
            .all()
        )
