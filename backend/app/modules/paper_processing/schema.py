from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.common.utils.drive_urls import drive_thumbnail_url, drive_view_url
from app.core.enums import (
    ExtractionConfidenceEnum,
    ImageSourceType,
    PdfTypeEnum,
    ProcessingStatusEnum,
    WatermarkStatusEnum,
)


class PaperProcessingJobCreate(BaseModel):
    subject_id: int
    title: str = Field(min_length=1, max_length=255)
    year: int = Field(ge=1900, le=2200)
    source_url: str | None = Field(default=None, max_length=1000)
    source_notes: str | None = None

    original_file_id: str
    original_mime_type: str | None = None
    original_file_size: int | None = None
    original_filename: str | None = None

    answer_file_id: str | None = None
    answer_mime_type: str | None = None
    answer_file_size: int | None = None
    answer_filename: str | None = None


class ExtractedOptionIn(BaseModel):
    label: str = Field(min_length=1, max_length=2)
    option_text: str = Field(min_length=1)


class ExtractedQuestionIn(BaseModel):
    """
    Payload for the review screen's edit/add actions. `correct_answer` is
    only ever populated by explicit admin input here - nothing upstream
    infers it.
    """
    question_number: int | None = None
    question_text: str = Field(min_length=1)
    correct_answer: str | None = Field(default=None, max_length=50)
    needs_review: bool | None = None
    options: list[ExtractedOptionIn] = []


class ExtractedOptionResponse(BaseModel):
    id: int
    label: str
    option_text: str

    model_config = ConfigDict(from_attributes=True)


class ExtractedQuestionImageResponse(BaseModel):
    id: int
    order_index: int
    file_id: str
    mime_type: str | None = None
    file_size: int | None = None
    filename: str | None = None
    source_type: ImageSourceType
    page_number: int | None = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def view_url(self) -> str | None:
        return drive_view_url(self.file_id)

    @computed_field
    @property
    def thumbnail_url(self) -> str | None:
        return drive_thumbnail_url(self.file_id)


class ExtractedQuestionResponse(BaseModel):
    id: int
    order_index: int
    question_number: int | None = None
    question_text: str
    raw_source_text: str | None = None
    confidence: ExtractionConfidenceEnum
    needs_review: bool
    correct_answer: str | None = None
    options: list[ExtractedOptionResponse] = []
    images: list[ExtractedQuestionImageResponse] = []

    model_config = ConfigDict(from_attributes=True)


class PaperProcessingJobStatusResponse(BaseModel):
    """Polled by the review page while the pipeline runs."""

    id: int
    status: ProcessingStatusEnum
    pdf_type: PdfTypeEnum | None = None
    ocr_used: bool
    watermark_status: WatermarkStatusEnum
    error_message: str | None = None
    questions_extracted: int
    questions_low_confidence: int
    paper_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class MergeRequest(BaseModel):
    """No payload - merging always uses the two blocks' own extracted text."""


class SplitRequest(BaseModel):
    """
    Optional character offset at which the admin wants the block cut. When
    omitted the block is duplicated into two editable halves for the admin
    to trim by hand - the server never guesses a split point.
    """
    split_at: int | None = None


class ExtractedQuestionImageAttach(BaseModel):
    """
    Payload for attaching or replacing a question image, mirroring the
    {file_id, mime_type, file_size, filename} shape `upload-widget.js`
    already produces via the existing /admin/upload endpoint - the same
    upload flow used everywhere else in the admin, not a new one.
    """
    file_id: str
    mime_type: str | None = None
    file_size: int | None = None
    filename: str | None = None


class ReassignImageRequest(BaseModel):
    target_question_id: int
