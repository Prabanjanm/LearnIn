from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import AlreadyExistsException, NotFoundException
from app.common.services.base_service import BaseService
from app.common.utils.slug import generate_slug

from .model import Exam
from .repository import ExamRepository
from .schema import ExamCreate


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


exam_service = ExamService()