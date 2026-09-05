from sqlalchemy.orm import Session, selectinload

from app.common.repositories.base_repository import BaseRepository
from app.core.enums import StatusEnum

from .model import Department


class DepartmentRepository(BaseRepository):

    def __init__(self):
        super().__init__(Department)

    def get_published_by_exam(
        self,
        db: Session,
        exam_id: int
    ):
        return (
            db.query(Department)
            .filter(
                Department.exam_id == exam_id,
                Department.status == StatusEnum.PUBLISHED,
            )
            .order_by(Department.display_order.asc(), Department.name.asc())
            .all()
        )

    def get_published_by_slug(
        self,
        db: Session,
        exam_id: int,
        slug: str
    ):
        return (
            db.query(Department)
            .filter(
                Department.exam_id == exam_id,
                Department.slug == slug,
                Department.status == StatusEnum.PUBLISHED,
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
            db.query(Department)
            .options(selectinload(Department.exam))
            .filter(
                Department.status == StatusEnum.PUBLISHED,
                Department.name.ilike(pattern),
            )
            .limit(limit)
            .all()
        )
