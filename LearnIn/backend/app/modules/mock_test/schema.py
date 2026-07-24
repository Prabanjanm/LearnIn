from pydantic import BaseModel, ConfigDict

from app.core.enums import StatusEnum


class MockTestBase(BaseModel):
    title: str
    description: str | None = None
    duration: int = 180
    total_marks: int = 100


class MockTestCreate(MockTestBase):
    paper_id: int
    question_ids: list[int] = []
    status: StatusEnum = StatusEnum.DRAFT


class MockTestResponse(MockTestBase):

    id: int
    paper_id: int
    total_questions: int
    status: StatusEnum

    model_config = ConfigDict(
        from_attributes=True
    )


class SubmittedAnswer(BaseModel):
    question_id: int
    answer: str


class MockTestSubmission(BaseModel):
    answers: list[SubmittedAnswer] = []


class QuestionResult(BaseModel):
    question_id: int
    is_correct: bool | None
    marks_awarded: float
    correct_answer: str
    explanation: str | None = None


class MockTestResult(BaseModel):
    mock_test_id: int
    total_marks: int
    scored_marks: float
    correct_count: int
    incorrect_count: int
    unanswered_count: int
    results: list[QuestionResult]
