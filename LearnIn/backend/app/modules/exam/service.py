from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import AlreadyExistsException, NotFoundException
from app.common.services.base_service import BaseService
from app.common.utils.file_tracking import cleanup_drive_file, collect_subtree_file_ids
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
    ):

        if self.repository.exists_by_code(db, data.code.upper()):

            raise AlreadyExistsException("Exam already exists")

        exam = Exam(

            name=data.name,

            code=data.code.upper(),

            slug=generate_slug(data.name),

            description=data.description,

            icon_file_id=data.icon_file_id,

            icon_mime_type=data.icon_mime_type,

            icon_file_size=data.icon_file_size,

            icon_filename=data.icon_filename,

            display_order=data.display_order,

            status=data.status,

        )

        return self.repository.create(
            db,
            exam
        )

    def get_published_by_slug(
        self,
        db: Session,
        slug: str
    ) -> Exam:

        exam = self.repository.get_published_by_slug(db, slug)

        if exam is None:
            raise NotFoundException("Exam not found")

        return exam

    def get_published_by_id(
        self,
        db: Session,
        exam_id: int
    ) -> Exam:

        exam = self.repository.get_published_by_id(db, exam_id)

        if exam is None:
            raise NotFoundException("Exam not found")

        return exam

    def get_published(
        self,
        db: Session
    ):
        return self.repository.get_published(db)

    def update_exam(
        self,
        db: Session,
        exam: Exam,
        data: ExamUpdate
    ) -> Exam:

        updates = data.model_dump(exclude_unset=True)

        if "code" in updates and updates["code"] is not None:
            new_code = updates["code"].upper()
            existing = self.repository.exists_by_code(db, new_code)
            if existing is not None and existing.id != exam.id:
                raise AlreadyExistsException("Exam already exists")
            updates["code"] = new_code

        if "name" in updates and updates["name"] is not None:
            updates["slug"] = generate_slug(updates["name"])

        old_icon_file_id = exam.icon_file_id
        replacing_icon = "icon_file_id" in updates and updates["icon_file_id"] != old_icon_file_id

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

        for file_id in file_ids:
            cleanup_drive_file(db, file_id)


exam_service = ExamService()