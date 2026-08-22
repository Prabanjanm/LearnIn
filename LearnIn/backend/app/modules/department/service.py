from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import AlreadyExistsException, NotFoundException
from app.common.services.base_service import BaseService
from app.common.utils.file_tracking import cleanup_drive_file, collect_subtree_file_ids
from app.common.utils.slug import generate_slug

from .model import Department
from .repository import DepartmentRepository
from .schema import DepartmentCreate, DepartmentUpdate


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

    def update_department(
        self,
        db: Session,
        department: Department,
        data: DepartmentUpdate
    ) -> Department:

        updates = data.model_dump(exclude_unset=True)

        if "code" in updates and updates["code"] is not None:
            new_code = updates["code"].upper()
            existing = self.repository.exists_by_code(db, department.exam_id, new_code)
            if existing is not None and existing.id != department.id:
                raise AlreadyExistsException("Department already exists for this exam")
            updates["code"] = new_code

        if "name" in updates and updates["name"] is not None:
            updates["slug"] = generate_slug(updates["name"])

        old_icon_file_id = department.icon_file_id
        replacing_icon = "icon_file_id" in updates and updates["icon_file_id"] != old_icon_file_id

        for field, value in updates.items():
            setattr(department, field, value)

        updated = self.repository.update(db, department)

        if replacing_icon:
            cleanup_drive_file(db, old_icon_file_id)

        return updated

    def delete_department(
        self,
        db: Session,
        department: Department
    ) -> None:
        file_ids = collect_subtree_file_ids(department)
        self.repository.delete(db, department)

        for file_id in file_ids:
            cleanup_drive_file(db, file_id)


department_service = DepartmentService()