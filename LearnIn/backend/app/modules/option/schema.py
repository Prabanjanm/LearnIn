from pydantic import BaseModel, ConfigDict, computed_field

from app.common.utils.drive_urls import drive_view_url


class OptionBase(BaseModel):
    label: str
    option_text: str
    image_file_id: str | None = None
    image_mime_type: str | None = None
    image_file_size: int | None = None
    image_filename: str | None = None


class OptionCreate(OptionBase):
    question_id: int


class OptionUpdate(BaseModel):
    label: str | None = None
    option_text: str | None = None
    image_file_id: str | None = None
    image_mime_type: str | None = None
    image_file_size: int | None = None
    image_filename: str | None = None


class OptionResponse(OptionBase):

    id: int
    question_id: int

    model_config = ConfigDict(
        from_attributes=True
    )

    @computed_field
    @property
    def image_url(self) -> str | None:
        return drive_view_url(self.image_file_id)
