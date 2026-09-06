from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import BaseModel
from app.core.enums import ConductedTestAttemptStatus, TerminationReason

if TYPE_CHECKING:
    from app.modules.conducted_test.model import ConductedTest
    from app.modules.question.model import Question
    from app.modules.student.model import Student


class ConductedTestAttempt(BaseModel):
    """
    One student's single, permanent attempt at one ConductedTest -
    UNIQUE(conducted_test_id, student_id) below is what actually enforces
    "one attempt per student" at the database level, not just in the
    service layer (a second /start racing the first loses the unique
    constraint, not a application-level check that could be bypassed by
    a concurrent request).

    started_at is set once, server-side, the moment the student's join
    is accepted - never trusted from the client. The grading deadline
    every student shares, however, is NOT this row's started_at; it's
    ConductedTest.scheduled_start_at + duration_minutes, fixed and
    identical for every attempt on the same conducted test (see
    conducted_test_attempt/service.py) - this is an institute exam
    slot, not a self-paced mock test.

    Answers are only ever autosaved into ConductedTestAttemptAnswer while
    status == IN_PROGRESS; is_correct/marks_awarded on those rows are
    filled in exactly once, at finalization, and the row is never touched
    again afterwards (status becomes terminal and stays terminal).
    """

    __tablename__ = "conducted_test_attempts"
    __table_args__ = (
        UniqueConstraint(
            "conducted_test_id", "student_id",
            name="uq_conducted_test_attempt_student",
        ),
    )

    conducted_test_id: Mapped[int] = mapped_column(
        ForeignKey("conducted_tests.id"),
        nullable=False,
        index=True
    )

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        nullable=False,
        index=True
    )

    # e.g. "LIN-R7K92X4" - an identifier for a result, not an access
    # token. Every result route still requires authentication +
    # ownership/creator-authorization checks (see
    # conducted_test_attempt/service.py) - knowing this value alone never
    # grants access.
    result_code: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True
    )

    status: Mapped[ConductedTestAttemptStatus] = mapped_column(
        Enum(ConductedTestAttemptStatus, name="conductedtestattemptstatus"),
        default=ConductedTestAttemptStatus.IN_PROGRESS,
        nullable=False,
        index=True
    )

    termination_reason: Mapped[TerminationReason | None] = mapped_column(
        Enum(TerminationReason, name="terminationreason"),
        nullable=True
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    time_taken_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    scored_marks: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_marks: Mapped[float | None] = mapped_column(Float, nullable=True)
    correct_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    incorrect_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unanswered_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    conducted_test: Mapped["ConductedTest"] = relationship()
    student: Mapped["Student"] = relationship()

    answers: Mapped[list["ConductedTestAttemptAnswer"]] = relationship(
        back_populates="attempt",
        cascade="all, delete-orphan",
        order_by="ConductedTestAttemptAnswer.id",
    )


class ConductedTestAttemptAnswer(BaseModel):
    """
    One question's answer within a ConductedTestAttempt. Unlike the
    generic MockTest engine (which splits an in-progress session's
    answers from a completed attempt's graded answers across two
    tables), a conducted test has exactly one attempt per student ever -
    so autosave (is_correct/marks_awarded still NULL) and the final
    graded state (filled in once, at submit) both live on this same row,
    with no separate "session" table needed.
    """

    __tablename__ = "conducted_test_attempt_answers"
    __table_args__ = (
        UniqueConstraint(
            "attempt_id", "question_id",
            name="uq_conducted_test_attempt_answer_question",
        ),
    )

    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("conducted_test_attempts.id"),
        nullable=False,
        index=True
    )

    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id"),
        nullable=False,
        index=True
    )

    selected_answer: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    is_correct: Mapped[bool | None] = mapped_column(nullable=True)

    marks_awarded: Mapped[float | None] = mapped_column(Float, nullable=True)

    attempt: Mapped["ConductedTestAttempt"] = relationship(back_populates="answers")
    question: Mapped["Question"] = relationship()
