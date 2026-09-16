import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ExtractionConfidenceEnum, PdfTypeEnum, ProcessingStatusEnum, QuestionType, WatermarkStatusEnum


class ConductedTestPaperJobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    original_file_id: str
    original_mime_type: str | None = None
    original_file_size: int | None = None
    original_filename: str | None = None


class ExtractedOptionIn(BaseModel):
    label: str = Field(min_length=1, max_length=2)
    option_text: str = Field(min_length=1)


class ExtractedQuestionIn(BaseModel):
    """Payload for the review screen's edit/add actions - mirrors
    paper_processing.schema.ExtractedQuestionIn exactly."""
    question_number: int | None = None
    question_text: str = Field(min_length=1)
    correct_answer: str | None = Field(default=None, max_length=50)
    needs_review: bool | None = None
    options: list[ExtractedOptionIn] = []


class ExtractedOptionResponse(BaseModel):
    id: uuid.UUID
    label: str
    option_text: str

    model_config = ConfigDict(from_attributes=True)


class ExtractedQuestionResponse(BaseModel):
    id: uuid.UUID
    order_index: int
    question_number: int | None = None
    question_text: str
    raw_source_text: str | None = None
    confidence: ExtractionConfidenceEnum
    needs_review: bool
    correct_answer: str | None = None
    options: list[ExtractedOptionResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ConductedTestPaperJobStatusResponse(BaseModel):
    """Polled by the status page while the pipeline runs."""

    id: uuid.UUID
    status: ProcessingStatusEnum
    pdf_type: PdfTypeEnum | None = None
    ocr_used: bool
    watermark_status: WatermarkStatusEnum
    error_message: str | None = None
    questions_extracted: int
    questions_low_confidence: int
    conducted_test_paper_id: uuid.UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class ConductedTestPaperResponse(BaseModel):
    id: uuid.UUID
    title: str
    total_questions: int

    model_config = ConfigDict(from_attributes=True)


class ConductedTestQuestionPublicResponse(BaseModel):
    """Student-facing shape for taking a conducted test sourced from an
    uploaded paper - deliberately omits correct_answer, mirroring
    QuestionPublicResponse (app.modules.question.schema) for the
    platform-MockTest path. Reuses ExtractedOptionResponse's shape for
    options (id/label/option_text) since ConductedTestOption carries the
    exact same fields."""

    id: uuid.UUID
    question_number: int
    question_type: QuestionType
    question_text: str
    marks: float
    negative_marks: float
    options: list[ExtractedOptionResponse] = []

    model_config = ConfigDict(from_attributes=True)
