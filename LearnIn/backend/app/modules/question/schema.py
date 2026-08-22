from pydantic import BaseModel, ConfigDict, computed_field

from app.common.utils.drive_urls import drive_view_url
from app.core.enums import DifficultyEnum, QuestionType, StatusEnum
from app.modules.option.schema import OptionResponse


class OptionIn(BaseModel):
    label: str
    option_text: str
    image_file_id: str | None = None
    image_mime_type: str | None = None
    image_file_size: int | None = None
    image_filename: str | None = None


class QuestionBase(BaseModel):
    question_number: int
    question_type: QuestionType
    question_text: str
    marks: float = 1
    negative_marks: float = 0
    difficulty: DifficultyEnum
    image_file_id: str | None = None
    image_mime_type: str | None = None
    image_file_size: int | None = None
    image_filename: str | None = None


class QuestionCreate(QuestionBase):
    paper_id: int
    correct_answer: str
    explanation: str | None = None
    explanation_image_file_id: str | None = None
    explanation_image_mime_type: str | None = None
    explanation_image_file_size: int | None = None
    explanation_image_filename: str | None = None
    options: list[OptionIn] = []
    status: StatusEnum = StatusEnum.DRAFT


class QuestionUpdate(BaseModel):
    question_number: int | None = None
    question_type: QuestionType | None = None
    question_text: str | None = None
    marks: float | None = None
    negative_marks: float | None = None
    difficulty: DifficultyEnum | None = None
    image_file_id: str | None = None
    image_mime_type: str | None = None
    image_file_size: int | None = None
    image_filename: str | None = None
    correct_answer: str | None = None
    explanation: str | None = None
    explanation_image_file_id: str | None = None
    explanation_image_mime_type: str | None = None
    explanation_image_file_size: int | None = None
    explanation_image_filename: str | None = None
    # None (the default) means "leave options untouched" - an explicit list,
    # even an empty one, replaces the full option set in one transaction.
    options: list[OptionIn] | None = None
    status: StatusEnum | None = None


class PublicOptionResponse(BaseModel):
    """Options without any hint of which one is correct."""

    id: int
    label: str
    option_text: str
    image_file_id: str | None = None
    image_filename: str | None = None

    model_config = ConfigDict(
        from_attributes=True
    )

    @computed_field
    @property
    def image_url(self) -> str | None:
        return drive_view_url(self.image_file_id)


class QuestionPublicResponse(QuestionBase):
    """Used for the practice/mock-test flow - never exposes the answer."""

    id: int
    paper_id: int
    options: list[PublicOptionResponse] = []

    model_config = ConfigDict(
        from_attributes=True
    )

    @computed_field
    @property
    def image_url(self) -> str | None:
        return drive_view_url(self.image_file_id)


class QuestionResponse(QuestionBase):
    """Admin-only view - includes the answer and explanation."""

    id: int
    paper_id: int
    correct_answer: str
    explanation: str | None = None
    explanation_image_file_id: str | None = None
    explanation_image_filename: str | None = None
    options: list[OptionResponse] = []
    status: StatusEnum

    model_config = ConfigDict(
        from_attributes=True
    )

    @computed_field
    @property
    def image_url(self) -> str | None:
        return drive_view_url(self.image_file_id)

    @computed_field
    @property
    def explanation_image_url(self) -> str | None:
        return drive_view_url(self.explanation_image_file_id)


class AnswerCheck(BaseModel):
    answer: str


class AnswerCheckResult(BaseModel):
    is_correct: bool
    correct_answer: str
    explanation: str | None = None
