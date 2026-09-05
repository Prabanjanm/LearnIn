from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import NotFoundException
from app.common.services.base_service import BaseService
from app.common.utils.file_tracking import cleanup_drive_file, cleanup_drive_files, collect_subtree_file_ids
from app.common.utils.slug import generate_slug

from .model import Exam
from .repository import ExamRepository
from .schema import ExamCreate, ExamUpdate


class ExamService(BaseService):

    def __init__(self):
        super().__init__(ExamRepository())

    def create_exam(
        self,
        db: Session,
        data: ExamCreate
    ) -> Exam:

        exam = Exam(
            name=data.name,
            code=data.code,
            description=data.description,
            display_order=data.display_order,
            icon_file_id=data.icon_file_id,
            icon_mime_type=data.icon_mime_type,
            icon_file_size=data.icon_file_size,
            icon_filename=data.icon_filename,
            status=data.status,
            slug=generate_slug(data.name),
        )

        return self.create(db, exam)

    def get_published(
        self,
        db: Session
    ):
        return self.repository.get_published(db)

    def get_published_by_id(
        self,
        db: Session,
        exam_id: int
    ) -> Exam:

        exam = self.repository.get_published_by_id(db, exam_id)

        if exam is None:
            raise NotFoundException("Exam not found")

        return exam

    def get_published_by_slug(
        self,
        db: Session,
        slug: str
    ) -> Exam:

        exam = self.repository.get_published_by_slug(db, slug)

        if exam is None:
            raise NotFoundException("Exam not found")

        return exam

    def update_exam(
        self,
        db: Session,
        exam: Exam,
        data: ExamUpdate
    ) -> Exam:

        updates = data.model_dump(exclude_unset=True)

        old_icon_file_id = exam.icon_file_id
        replacing_icon = "icon_file_id" in updates and updates["icon_file_id"] != old_icon_file_id

        if "name" in updates and updates["name"] != exam.name:
            updates.setdefault("slug", generate_slug(updates["name"]))

        for field, value in updates.items():
            setattr(exam, field, value)

        updated = self.repository.update(db, exam)

        if replacing_icon:
            cleanup_drive_file(db, old_icon_file_id)

        return updated

    def delete_exam(
        self,
        db: Session,
        exam: Exam
    ) -> None:
        file_ids = collect_subtree_file_ids(exam)
        self.repository.delete(db, exam)
        cleanup_drive_files(db, file_ids)


exam_service = ExamService()
