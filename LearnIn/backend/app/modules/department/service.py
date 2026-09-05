from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import NotFoundException
from app.common.services.base_service import BaseService
from app.common.utils.file_tracking import cleanup_drive_file, cleanup_drive_files, collect_subtree_file_ids
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

        department = Department(
            exam_id=data.exam_id,
            name=data.name,
            code=data.code,
            display_order=data.display_order,
            icon_file_id=data.icon_file_id,
            icon_mime_type=data.icon_mime_type,
            icon_file_size=data.icon_file_size,
            icon_filename=data.icon_filename,
            status=data.status,
            slug=generate_slug(data.name),
        )

        return self.create(db, department)

    def get_published_by_exam(
        self,
        db: Session,
        exam_id: int
    ):
        return self.repository.get_published_by_exam(db, exam_id)

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

    def update_department(
        self,
        db: Session,
        department: Department,
        data: DepartmentUpdate
    ) -> Department:

        updates = data.model_dump(exclude_unset=True)

        old_icon_file_id = department.icon_file_id
        replacing_icon = "icon_file_id" in updates and updates["icon_file_id"] != old_icon_file_id

        if "name" in updates and updates["name"] != department.name:
            updates.setdefault("slug", generate_slug(updates["name"]))

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
        cleanup_drive_files(db, file_ids)


department_service = DepartmentService()
