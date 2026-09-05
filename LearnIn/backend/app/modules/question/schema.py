from pydantic import BaseModel, ConfigDict, computed_field

from app.common.utils.drive_urls import drive_view_url
from app.core.enums import DifficultyEnum, QuestionType, StatusEnum
from app.modules.option.schema import OptionResponse


class OptionIn(BaseModel):
    """
    One option row as submitted alongside a question create/update - unlike
    OptionCreate/OptionUpdate (app.modules.option.schema) this carries no
    question_id, since the question service assigns it while syncing the
    full option set for the question in one go.
    """

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
    correct_answer: str
    difficulty: DifficultyEnum
    marks: float = 1
    negative_marks: float = 0
    explanation: str | None = None


class QuestionCreate(QuestionBase):
    paper_id: int
    image_file_id: str | None = None
    image_mime_type: str | None = None
    image_file_size: int | None = None
    image_filename: str | None = None
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
    correct_answer: str | None = None
    difficulty: DifficultyEnum | None = None
    marks: float | None = None
    negative_marks: float | None = None
    explanation: str | None = None
    image_file_id: str | None = None
    image_mime_type: str | None = None
    image_file_size: int | None = None
    image_filename: str | None = None
    explanation_image_file_id: str | None = None
    explanation_image_mime_type: str | None = None
    explanation_image_file_size: int | None = None
    explanation_image_filename: str | None = None
    options: list[OptionIn] | None = None
    status: StatusEnum | None = None


class QuestionResponse(QuestionBase):

    id: int
    paper_id: int
    image_file_id: str | None = None
    image_mime_type: str | None = None
    image_file_size: int | None = None
    image_filename: str | None = None
    explanation_image_file_id: str | None = None
    explanation_image_mime_type: str | None = None
    explanation_image_file_size: int | None = None
    explanation_image_filename: str | None = None
    status: StatusEnum
    options: list[OptionResponse] = []

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


class QuestionCheckRequest(BaseModel):
    answer: str


class QuestionCheckResponse(BaseModel):
    is_correct: bool
    correct_answer: str
    explanation: str | None = None


class QuestionPublicResponse(BaseModel):
    """
    Student-facing shape for taking a mock test - deliberately omits
    correct_answer/explanation/explanation_image_* so the answer key isn't
    shipped to the browser before the test is submitted.
    """

    id: int
    question_number: int
    question_type: QuestionType
    question_text: str
    difficulty: DifficultyEnum
    marks: float
    negative_marks: float
    image_file_id: str | None = None
    options: list[OptionResponse] = []

    model_config = ConfigDict(
        from_attributes=True
    )

    @computed_field
    @property
    def image_url(self) -> str | None:
        return drive_view_url(self.image_file_id)
