import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.enums import StatusEnum


class ConductedTestCreate(BaseModel):
    """Exactly one question source: an existing platform MockTest, or
    one of this institution's own uploaded/confirmed papers (see
    conducted_test_paper/model.py - ConductedTestPaper). Mirrors the
    ConductedTest.__table_args__ CheckConstraint - enforced here too so
    a bad request is rejected with a clear 422 instead of a raw DB
    constraint error."""

    mock_test_id: uuid.UUID | None = None
    conducted_test_paper_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    instructions: str | None = None
    duration_minutes: int = Field(gt=0, le=600)
    scheduled_start_at: datetime

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "ConductedTestCreate":
        if (self.mock_test_id is None) == (self.conducted_test_paper_id is None):
            raise ValueError("Provide exactly one of mock_test_id or conducted_test_paper_id")
        return self

    @field_validator("scheduled_start_at")
    @classmethod
    def _must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("scheduled_start_at must include a timezone")
        return value


class ConductedTestUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    instructions: str | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=600)
    scheduled_start_at: datetime | None = None


class ConductedTestResponse(BaseModel):
    id: uuid.UUID
    mock_test_id: uuid.UUID | None
    conducted_test_paper_id: uuid.UUID | None
    title: str
    instructions: str | None
    test_code: str
    duration_minutes: int
    scheduled_start_at: datetime
    status: StatusEnum
    institution_id: uuid.UUID
    created_by_institution_user_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConductedTestParticipantResponse(BaseModel):
    """One row of the institute results dashboard - never includes
    another student's answers, only summary/report-level fields."""

    student_id: uuid.UUID
    student_name: str | None
    student_email: str
    result_code: str
    status: str
    termination_reason: str | None
    started_at: datetime
    submitted_at: datetime | None
    scored_marks: float | None
    total_marks: float | None
    percentage: float | None
