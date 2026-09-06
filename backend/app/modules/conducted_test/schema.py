from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import StatusEnum


class ConductedTestCreate(BaseModel):
    mock_test_id: int
    title: str = Field(min_length=1, max_length=255)
    instructions: str | None = None
    duration_minutes: int = Field(gt=0, le=600)
    scheduled_start_at: datetime

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
    id: int
    mock_test_id: int
    title: str
    instructions: str | None
    test_code: str
    duration_minutes: int
    scheduled_start_at: datetime
    status: StatusEnum
    institution_id: int
    created_by_institution_user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConductedTestParticipantResponse(BaseModel):
    """One row of the institute results dashboard - never includes
    another student's answers, only summary/report-level fields."""

    student_id: int
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
