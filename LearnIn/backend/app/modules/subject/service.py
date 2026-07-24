from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import NotFoundException
from app.common.services.base_service import BaseService
from app.common.utils.slug import generate_slug

from .model import Subject
from .repository import SubjectRepository
from .schema import SubjectCreate


class SubjectService(BaseService):

    def __init__(self):
        super().__init__(SubjectRepository())

    def create_subject(
        self,
        db: Session,
        data: SubjectCreate
    ) -> Subject:

        subject = Subject(
            department_id=data.department_id,
            name=data.name,
            slug=generate_slug(data.name),
            display_order=data.display_order,
            icon_file_id=data.icon_file_id,
            icon_mime_type=data.icon_mime_type,
            icon_file_size=data.icon_file_size,
            icon_filename=data.icon_filename,
            status=data.status,
        )

        return self.repository.create(db, subject)

    def get_published_by_department(
        self,
        db: Session,
        department_id: int
    ):
        return self.repository.get_published_by_department(db, department_id)

    def get_published_by_slug(
        self,
        db: Session,
        department_id: int,
        slug: str
    ) -> Subject:

        subject = self.repository.get_published_by_slug(db, department_id, slug)

        if subject is None:
            raise NotFoundException("Subject not found")

        return subject

    def get_published_by_id(
        self,
        db: Session,
        subject_id: int
    ) -> Subject:

        subject = self.repository.get_published_by_id(db, subject_id)

        if subject is None:
            raise NotFoundException("Subject not found")

        return subject


subject_service = SubjectService()
