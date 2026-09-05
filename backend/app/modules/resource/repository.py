from sqlalchemy.orm import Session, selectinload

from app.common.repositories.base_repository import BaseRepository
from app.core.enums import StatusEnum
from app.modules.department.model import Department
from app.modules.subject.model import Subject

from .model import Resource


class ResourceRepository(BaseRepository):

    def __init__(self):
        super().__init__(Resource)

    def get_published_by_subject(
        self,
        db: Session,
        subject_id: int
    ):
        return (
            db.query(Resource)
            .filter(
                Resource.subject_id == subject_id,
                Resource.status == StatusEnum.PUBLISHED,
            )
            .order_by(Resource.created_at.desc())
            .all()
        )

    def get_published_by_id(
        self,
        db: Session,
        resource_id: int
    ):
        return (
            db.query(Resource)
            .filter(
                Resource.id == resource_id,
                Resource.status == StatusEnum.PUBLISHED,
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
            db.query(Resource)
            .options(
                selectinload(Resource.subject)
                .selectinload(Subject.department)
                .selectinload(Department.exam)
            )
            .filter(
                Resource.status == StatusEnum.PUBLISHED,
                Resource.title.ilike(pattern),
            )
            .limit(limit)
            .all()
        )
