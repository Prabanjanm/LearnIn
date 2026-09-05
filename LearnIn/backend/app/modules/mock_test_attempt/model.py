from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import BaseModel

if TYPE_CHECKING:
    from app.modules.mock_test.model import MockTest
    from app.modules.question.model import Question
    from app.modules.student.model import Student


class MockTestSession(BaseModel):
    """
    The authoritative record of when a student started a mock test -
    created once, at the moment "Start Test" first calls the backend, and
    never modified afterwards. This is what makes the timer
    server-authoritative: `started_at` lives here (server clock, set by
    the DB default), not in the browser, so a refresh or an edited
    localStorage value can't move it. `client_token` is the same
    randomUUID the browser already generates for submission idempotency
    (see MockTestAttempt.client_token) - reusing it here means "Start" is
    naturally idempotent too: calling it again with the same token (a
    refresh, or a second tab sharing the same localStorage) returns the
    *original* started_at instead of resetting the clock.
    """

    __tablename__ = "mock_test_sessions"
    __table_args__ = (
        UniqueConstraint(
            "mock_test_id", "client_token",
            name="uq_mock_test_session_client_token",
        ),
    )

    mock_test_id: Mapped[int] = mapped_column(
        ForeignKey("mock_tests.id"),
        nullable=False,
        index=True
    )

    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("students.id"),
        nullable=True,
        index=True
    )

    client_token: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    mock_test: Mapped["MockTest"] = relationship()
    student: Mapped["Student | None"] = relationship()

    session_answers: Mapped[list["MockTestSessionAnswer"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class MockTestSessionAnswer(BaseModel):
    """
    One question's in-progress answer + mark-for-review state within an
    active (not yet submitted) MockTestSession. This is what makes an
    active test resumable from the server rather than only from
    localStorage: every "Save & Next" / "Mark for Review" / "Clear
    Answer" persists here immediately, so a refresh, a closed tab, or a
    cleared localStorage all resume from the same authoritative state.
    Deliberately does NOT store is_correct/marks_awarded - correctness is
    only ever computed once, at submission, from MockTestAttemptAnswer;
    this table only ever holds what the student selected.
    """

    __tablename__ = "mock_test_session_answers"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "question_id",
            name="uq_mock_test_session_answer_question",
        ),
    )

    session_id: Mapped[int] = mapped_column(
        ForeignKey("mock_test_sessions.id"),
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

    is_marked: Mapped[bool] = mapped_column(
        default=False,
        nullable=False
    )

    session: Mapped["MockTestSession"] = relationship(back_populates="session_answers")
    question: Mapped["Question"] = relationship()


class MockTestAttempt(BaseModel):
    """
    One student's completed run of a mock test. student_id is nullable
    because anonymous (logged-out) attempts are still allowed - those are
    identified only by the attempt id in the result page URL, an
    "unguessable-enough private link". A logged-in student's attempt is
    additionally checked for ownership on the result page
    (pages/router.py mock_test_result_page) so one student can't view
    another's answers/score by guessing/incrementing the id.
    """

    __tablename__ = "mock_test_attempts"
    __table_args__ = (
        UniqueConstraint(
            "mock_test_id", "client_token",
            name="uq_mock_test_attempt_client_token",
        ),
    )

    mock_test_id: Mapped[int] = mapped_column(
        ForeignKey("mock_tests.id"),
        nullable=False,
        index=True
    )

    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("students.id"),
        nullable=True,
        index=True
    )

    client_token: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True
    )

    time_taken_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    scored_marks: Mapped[float] = mapped_column(Float, nullable=False)
    total_marks: Mapped[float] = mapped_column(Float, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False)
    incorrect_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unanswered_count: Mapped[int] = mapped_column(Integer, nullable=False)

    mock_test: Mapped["MockTest"] = relationship()
    student: Mapped["Student | None"] = relationship()

    answers: Mapped[list["MockTestAttemptAnswer"]] = relationship(
        back_populates="attempt",
        cascade="all, delete-orphan",
        order_by="MockTestAttemptAnswer.id",
    )


class MockTestAttemptAnswer(BaseModel):

    __tablename__ = "mock_test_attempt_answers"

    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("mock_test_attempts.id"),
        nullable=False,
        index=True
    )

    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id"),
        nullable=False,
        index=True
    )

    submitted_answer: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    is_correct: Mapped[bool | None] = mapped_column(nullable=True)
    marks_awarded: Mapped[float] = mapped_column(Float, nullable=False)

    attempt: Mapped["MockTestAttempt"] = relationship(back_populates="answers")
    question: Mapped["Question"] = relationship()
