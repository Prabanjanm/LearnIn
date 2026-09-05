from pydantic import BaseModel, ConfigDict, computed_field

from app.common.utils.drive_urls import drive_view_url
from app.core.enums import StatusEnum


class ExamBase(BaseModel):
    name: str
    code: str
    description: str | None = None


class ExamCreate(ExamBase):
    display_order: int = 0
    icon_file_id: str | None = None
    icon_mime_type: str | None = None
    icon_file_size: int | None = None
    icon_filename: str | None = None
    status: StatusEnum = StatusEnum.DRAFT


class ExamUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None
    display_order: int | None = None
    icon_file_id: str | None = None
    icon_mime_type: str | None = None
    icon_file_size: int | None = None
    icon_filename: str | None = None
    status: StatusEnum | None = None


class ExamResponse(ExamBase):

    id: int
    slug: str
    display_order: int
    icon_file_id: str | None = None
    icon_filename: str | None = None
    status: StatusEnum
    meta_title: str | None = None
    meta_description: str | None = None

    model_config = ConfigDict(
        from_attributes=True
    )

    @computed_field
    @property
    def icon_url(self) -> str | None:
        return drive_view_url(self.icon_file_id)
