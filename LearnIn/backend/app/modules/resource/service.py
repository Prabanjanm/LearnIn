from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import NotFoundException
from app.common.services.base_service import BaseService

from .model import Resource
from .repository import ResourceRepository
from .schema import ResourceCreate


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


resource_service = ResourceService()
