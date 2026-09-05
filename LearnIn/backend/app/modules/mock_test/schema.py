from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import StatusEnum
from app.modules.question.schema import QuestionPublicResponse


class MockTestBase(BaseModel):
    title: str
    description: str | None = None
    duration: int = 180
    total_marks: int = 100


class MockTestCreate(MockTestBase):
    paper_id: int
    question_ids: list[int] = []
    status: StatusEnum = StatusEnum.DRAFT


class MockTestUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    duration: int | None = None
    total_marks: int | None = None
    status: StatusEnum | None = None


class MockTestResponse(MockTestBase):

    id: int
    paper_id: int
    total_questions: int
    status: StatusEnum

    model_config = ConfigDict(
        from_attributes=True
    )


class MockTestQuestionEntry(BaseModel):
    """One row of GET /{id}/questions - shape matches what mock_test.js
    already expects (`entry.question`), a thin wrapper in case ordering
    metadata needs to be exposed to the frontend later."""

    question: QuestionPublicResponse


class MockTestSubmitAnswer(BaseModel):
    question_id: int
    answer: str


class MockTestSubmitRequest(BaseModel):
    answers: list[MockTestSubmitAnswer] = []
    client_token: str | None = Field(default=None, max_length=64)
    # No time_taken_seconds field here on purpose: how long the attempt
    # took is now computed server-side from the MockTestSession this
    # client_token started (see mock_test_service.submit_attempt) - a
    # client-reported duration is never trusted for anything.


class MockTestStartRequest(BaseModel):
    client_token: str = Field(max_length=64)


class MockTestStartResponse(BaseModel):
    client_token: str
    duration_seconds: int
    started_at: str
    deadline: str
    remaining_seconds: int
    submitted: bool
    attempt_id: int | None = None
    answers: dict[int, str]
    marked: list[int]


class MockTestAnswerRequest(BaseModel):
    client_token: str = Field(max_length=64)
    question_id: int
    answer: str = ""
    marked: bool = False


class MockTestSubmitResultItem(BaseModel):
    question_id: int
    is_correct: bool | None
    correct_answer: str
    explanation: str | None = None
    marks_awarded: float


class MockTestSubmitResponse(BaseModel):
    attempt_id: int
    scored_marks: float
    total_marks: float
    correct_count: int
    incorrect_count: int
    unanswered_count: int
    results: list[MockTestSubmitResultItem]
