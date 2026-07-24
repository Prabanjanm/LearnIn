from pydantic import BaseModel, ConfigDict, computed_field

from app.common.utils.drive_urls import drive_view_url
from app.core.enums import StatusEnum


class DepartmentCreate(BaseModel):
    exam_id: int
    name: str
    code: str
    display_order: int = 0
    icon_file_id: str | None = None
    icon_mime_type: str | None = None
    icon_file_size: int | None = None
    icon_filename: str | None = None
    status: StatusEnum = StatusEnum.DRAFT


class DepartmentResponse(BaseModel):

    id: int
    exam_id: int
    name: str
    code: str
    slug: str
    display_order: int
    status: StatusEnum
    icon_file_id: str | None = None
    icon_filename: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None

    model_config = ConfigDict(
        from_attributes=True
    )

    @computed_field
    @property
    def icon_url(self) -> str | None:
        return drive_view_url(self.icon_file_id)
