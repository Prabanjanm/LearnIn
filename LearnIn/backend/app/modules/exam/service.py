from sqlalchemy.orm import Session

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

        if self.repository.exists_by_code(db, data.code):

            raise Exception("Exam already exists")

        exam = Exam(

            name=data.name,

            code=data.code.upper(),

            slug=generate_slug(data.name),

            description=data.description,

            icon=data.icon,

            display_order=data.display_order

        )

        return self.repository.create(
            db,
            exam
        )


exam_service = ExamService()