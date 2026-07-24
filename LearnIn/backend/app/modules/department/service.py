from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import AlreadyExistsException, NotFoundException
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
    ) -> Department:

        if self.repository.exists_by_code(db, data.exam_id, data.code.upper()):
            raise AlreadyExistsException("Department already exists for this exam")

        department = Department(

            exam_id=data.exam_id,

            name=data.name,

            code=data.code.upper(),

            slug=generate_slug(data.name),

            display_order=data.display_order,

            icon_file_id=data.icon_file_id,

            icon_mime_type=data.icon_mime_type,

            icon_file_size=data.icon_file_size,

            icon_filename=data.icon_filename,

            status=data.status,

        )

        return self.repository.create(
            db,
            department
        )

    def get_published_by_exam(
        self,
        db: Session,
        exam_id: int
    ):
        return self.repository.get_published_by_exam(
            db,
            exam_id
        )

    def get_published_by_slug(
        self,
        db: Session,
        exam_id: int,
        slug: str
    ) -> Department:

        department = self.repository.get_published_by_slug(db, exam_id, slug)

        if department is None:
            raise NotFoundException("Department not found")

        return department

    def get_published_by_id(
        self,
        db: Session,
        department_id: int
    ) -> Department:

        department = self.repository.get_published_by_id(db, department_id)

        if department is None:
            raise NotFoundException("Department not found")

        return department


department_service = DepartmentService()