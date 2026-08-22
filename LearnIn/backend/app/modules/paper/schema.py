from pydantic import BaseModel, ConfigDict, computed_field

from app.common.utils.drive_urls import drive_download_url, drive_view_url
from app.core.enums import StatusEnum


class PaperBase(BaseModel):
    title: str
    year: int
    duration: int | None = None


class PaperCreate(PaperBase):
    subject_id: int
    question_file_id: str
    question_file_mime_type: str | None = None
    question_file_size: int | None = None
    question_filename: str | None = None
    answer_file_id: str | None = None
    answer_file_mime_type: str | None = None
    answer_file_size: int | None = None
    answer_filename: str | None = None
    status: StatusEnum = StatusEnum.DRAFT


class PaperUpdate(BaseModel):
    title: str | None = None
    duration: int | None = None
    question_file_id: str | None = None
    question_file_mime_type: str | None = None
    question_file_size: int | None = None
    question_filename: str | None = None
    answer_file_id: str | None = None
    answer_file_mime_type: str | None = None
    answer_file_size: int | None = None
    answer_filename: str | None = None
    status: StatusEnum | None = None


class PaperResponse(PaperBase):

    id: int
    subject_id: int
    question_file_id: str
    question_filename: str | None = None
    answer_file_id: str | None = None
    answer_filename: str | None = None
    total_questions: int
    status: StatusEnum

    model_config = ConfigDict(
        from_attributes=True
    )

    @computed_field
    @property
    def question_file_view_url(self) -> str | None:
        return drive_view_url(self.question_file_id)

    @computed_field
    @property
    def question_file_download_url(self) -> str | None:
        return drive_download_url(self.question_file_id)

    @computed_field
    @property
    def answer_file_view_url(self) -> str | None:
        return drive_view_url(self.answer_file_id)
