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
            .order_by(Subject.display_order.asc(), Subject.name.asc())
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

    def get_filtered(
        self,
        db: Session,
        exam_id: int | None = None,
        department_id: int | None = None,
        term: str | None = None,
        page: int = 1,
        page_size: int = 24,
    ):
        """Powers the /practice discovery page - only real filters (exam,
        department, name search) on real columns/relationships."""
        query = (
            db.query(Subject)
            .join(Department, Subject.department_id == Department.id)
            .options(selectinload(Subject.department).selectinload(Department.exam))
            .filter(Subject.status == StatusEnum.PUBLISHED)
        )

        if exam_id is not None:
            query = query.filter(Department.exam_id == exam_id)
        if department_id is not None:
            query = query.filter(Subject.department_id == department_id)
        if term:
            query = query.filter(Subject.name.ilike(f"%{term}%"))

        query = query.order_by(Subject.name.asc())

        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return items, total

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
                selectinload(Subject.department)
                .selectinload(Department.exam)
            )
            .filter(
                Subject.status == StatusEnum.PUBLISHED,
                Subject.name.ilike(pattern),
            )
            .limit(limit)
            .all()
        )
