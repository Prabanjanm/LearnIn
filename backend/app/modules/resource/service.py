from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import NotFoundException
from app.common.services.base_service import BaseService
from app.common.utils.file_tracking import cleanup_drive_file

from .model import Resource
from .repository import ResourceRepository
from .schema import ResourceCreate, ResourceUpdate


class ResourceService(BaseService):

    def __init__(self):
        super().__init__(ResourceRepository())

    def create_resource(
        self,
        db: Session,
        data: ResourceCreate
    ) -> Resource:

        resource = Resource(
            subject_id=data.subject_id,
            title=data.title,
            description=data.description,
            resource_type=data.resource_type,
            google_drive_file_id=data.google_drive_file_id,
            google_drive_mime_type=data.google_drive_mime_type,
            google_drive_file_size=data.google_drive_file_size,
            google_drive_filename=data.google_drive_filename,
            status=data.status,
        )

        return self.repository.create(db, resource)

    def get_published_by_subject(
        self,
        db: Session,
        subject_id: int
    ):
        return self.repository.get_published_by_subject(db, subject_id)

    def get_published_by_id(
        self,
        db: Session,
        resource_id: int
    ) -> Resource:

        resource = self.repository.get_published_by_id(db, resource_id)

        if resource is None:
            raise NotFoundException("Resource not found")

        return resource

    def update_resource(
        self,
        db: Session,
        resource: Resource,
        data: ResourceUpdate
    ) -> Resource:

        updates = data.model_dump(exclude_unset=True)

        old_file_id = resource.google_drive_file_id
        replacing_file = "google_drive_file_id" in updates and updates["google_drive_file_id"] != old_file_id

        for field, value in updates.items():
            setattr(resource, field, value)

        updated = self.repository.update(db, resource)

        if replacing_file:
            cleanup_drive_file(db, old_file_id)

        return updated

    def delete_resource(
        self,
        db: Session,
        resource: Resource
    ) -> None:
        file_id = resource.google_drive_file_id
        self.repository.delete(db, resource)
        cleanup_drive_file(db, file_id)


resource_service = ResourceService()
