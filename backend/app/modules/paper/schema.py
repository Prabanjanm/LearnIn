from pydantic import BaseModel, ConfigDict, computed_field

from app.common.utils.drive_urls import drive_download_url, drive_view_url
from app.core.enums import StatusEnum


class PaperBase(BaseModel):
    title: str
    year: int


class PaperCreate(PaperBase):
    subject_id: int
    question_file_id: str
    question_file_mime_type: str | None = None
    # Note: the admin CRUD engine's generic upload-field expansion
    # (apply_upload_field in app/modules/admin/crud_config.py) derives the
    # size key as f"{metadata_prefix}_file_size". Paper's metadata_prefix
    # for this field is "question_file" (needed so mime_type comes out as
    # question_file_mime_type), which makes the derived size key
    # "question_file_file_size" - not the actual question_file_size column.
    # Accept that exact key here and map it onto the real column in the
    # service layer, rather than touching the shared admin engine.
    question_file_file_size: int | None = None
    question_filename: str | None = None
    answer_file_id: str | None = None
    answer_file_mime_type: str | None = None
    answer_file_file_size: int | None = None
    answer_filename: str | None = None
    duration: int | None = None
    total_questions: int = 0
    status: StatusEnum = StatusEnum.DRAFT


class PaperUpdate(BaseModel):
    subject_id: int | None = None
    title: str | None = None
    year: int | None = None
    question_file_id: str | None = None
    question_file_mime_type: str | None = None
    question_file_file_size: int | None = None
    question_filename: str | None = None
    answer_file_id: str | None = None
    answer_file_mime_type: str | None = None
    answer_file_file_size: int | None = None
    answer_filename: str | None = None
    duration: int | None = None
    total_questions: int | None = None
    status: StatusEnum | None = None


class PaperResponse(PaperBase):

    id: int
    subject_id: int
    question_file_id: str
    question_filename: str | None = None
    answer_file_id: str | None = None
    answer_filename: str | None = None
    duration: int | None = None
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

    @computed_field
    @property
    def answer_file_download_url(self) -> str | None:
        return drive_download_url(self.answer_file_id)
