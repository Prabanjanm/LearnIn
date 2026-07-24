from pydantic import BaseModel, ConfigDict, computed_field

from app.common.utils.drive_urls import drive_download_url, drive_view_url
from app.core.enums import ResourceType, StatusEnum


class ResourceBase(BaseModel):
    title: str
    description: str | None = None
    resource_type: ResourceType


class ResourceCreate(ResourceBase):
    subject_id: int
    google_drive_file_id: str
    google_drive_mime_type: str | None = None
    google_drive_file_size: int | None = None
    google_drive_filename: str | None = None
    status: StatusEnum = StatusEnum.DRAFT


class ResourceResponse(ResourceBase):

    id: int
    subject_id: int
    google_drive_file_id: str
    google_drive_filename: str | None = None
    status: StatusEnum

    model_config = ConfigDict(
        from_attributes=True
    )

    @computed_field
    @property
    def view_url(self) -> str | None:
        return drive_view_url(self.google_drive_file_id)

    @computed_field
    @property
    def download_url(self) -> str | None:
        return drive_download_url(self.google_drive_file_id)
