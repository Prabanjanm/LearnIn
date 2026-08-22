from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import NotFoundException
from app.common.services.base_service import BaseService
from app.common.utils.file_tracking import cleanup_drive_file, collect_subtree_file_ids
from app.common.utils.slug import generate_slug

from .model import Subject
from .repository import SubjectRepository
from .schema import SubjectCreate, SubjectUpdate


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

    def update_subject(
        self,
        db: Session,
        subject: Subject,
        data: SubjectUpdate
    ) -> Subject:

        updates = data.model_dump(exclude_unset=True)

        if "name" in updates and updates["name"] is not None:
            updates["slug"] = generate_slug(updates["name"])

        old_icon_file_id = subject.icon_file_id
        replacing_icon = "icon_file_id" in updates and updates["icon_file_id"] != old_icon_file_id

        for field, value in updates.items():
            setattr(subject, field, value)

        updated = self.repository.update(db, subject)

        if replacing_icon:
            cleanup_drive_file(db, old_icon_file_id)

        return updated

    def delete_subject(
        self,
        db: Session,
        subject: Subject
    ) -> None:
        file_ids = collect_subtree_file_ids(subject)
        self.repository.delete(db, subject)

        for file_id in file_ids:
            cleanup_drive_file(db, file_id)


subject_service = SubjectService()
