from sqlalchemy.orm import Session

from app.common.services.base_service import BaseService
from app.common.utils.slug import generate_slug

from .model import Department
from .repository import DepartmentRepository
from .schema import DepartmentCreate


class DepartmentService(BaseService):

    def __init__(self):
        super().__init__(DepartmentRepository())

    def create_department(
        self,
        db: Session,
        data: DepartmentCreate
    ):

        department = Department(

            exam_id=data.exam_id,

            name=data.name,

            code=data.code.upper(),

            slug=generate_slug(data.name),

            display_order=data.display_order

        )

        return self.repository.create(
            db,
            department
        )

    def get_by_exam(
        self,
        db: Session,
        exam_id: int
    ):
        return self.repository.get_by_exam(
            db,
            exam_id
        )


department_service = DepartmentService()