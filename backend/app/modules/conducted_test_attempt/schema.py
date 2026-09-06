from datetime import datetime

from pydantic import BaseModel, Field


class JoinTestRequest(BaseModel):
    test_code: str = Field(min_length=1, max_length=20)


class JoinTestResponse(BaseModel):
    """Instructions-screen payload - deliberately excludes questions/
    answers, only enough to render the security-warning + accept-rules
    screen before the student has actually started the timed window."""

    conducted_test_id: int
    title: str
    instructions: str | None
    duration_minutes: int
    scheduled_start_at: datetime
    window_ends_at: datetime
    already_completed: bool


class StartAttemptResponse(BaseModel):
    attempt_id: int
    remaining_seconds: int
    window_ends_at: datetime
    questions: list[dict]
    answers: dict[int, str]


class SaveAnswerRequest(BaseModel):
    question_id: int
    answer: str = ""


class ViolationRequest(BaseModel):
    reason: str = Field(pattern="^(TAB_SWITCH|FULLSCREEN_EXIT)$")


class SubmitResponse(BaseModel):
    attempt_id: int
    result_code: str
    status: str
    termination_reason: str | None
    scored_marks: float
    total_marks: float
    correct_count: int
    incorrect_count: int
    unanswered_count: int


class SubjectBreakdown(BaseModel):
    subject: str
    questions: int
    correct: int
    incorrect: int
    accuracy: float | None
    score: float


class ResultReportResponse(BaseModel):
    result_code: str
    test_title: str
    student_name: str | None
    student_email: str
    started_at: datetime
    submitted_at: datetime | None
    duration_minutes: int
    time_taken_seconds: int | None
    total_questions: int
    attempted: int
    correct_count: int
    incorrect_count: int
    unanswered_count: int
    scored_marks: float
    total_marks: float
    percentage: float | None
    status: str
    termination_reason: str | None
    subject_breakdown: list[SubjectBreakdown]


class MyResultListItem(BaseModel):
    test_title: str
    result_code: str
    started_at: datetime
    submitted_at: datetime | None
    scored_marks: float | None
    total_marks: float | None
    percentage: float | None
    status: str
