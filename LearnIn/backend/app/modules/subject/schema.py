from pydantic import BaseModel, ConfigDict, computed_field

from app.common.utils.drive_urls import drive_view_url
from app.core.enums import StatusEnum


class SubjectBase(BaseModel):
    name: str
    display_order: int = 0


class SubjectCreate(SubjectBase):
    department_id: int
    icon_file_id: str | None = None
    icon_mime_type: str | None = None
    icon_file_size: int | None = None
    icon_filename: str | None = None
    status: StatusEnum = StatusEnum.DRAFT


class SubjectUpdate(BaseModel):
    name: str | None = None
    display_order: int | None = None
    icon_file_id: str | None = None
    icon_mime_type: str | None = None
    icon_file_size: int | None = None
    icon_filename: str | None = None
    status: StatusEnum | None = None


class SubjectResponse(SubjectBase):

    id: int
    department_id: int
    slug: str
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
