from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import InvalidStateException, NotFoundException
from app.common.services.base_service import BaseService
from app.modules.mock_test_question.service import mock_test_question_service
from app.modules.question.service import question_service

from .model import MockTestAttempt, MockTestAttemptAnswer, MockTestSession, MockTestSessionAnswer
from .repository import MockTestAttemptRepository, MockTestSessionRepository


class MockTestAttemptService(BaseService):

    def __init__(self):
        super().__init__(MockTestAttemptRepository())

    def record_attempt(
        self,
        db: Session,
        mock_test_id: int,
        time_taken_seconds: int | None,
        scored_marks: float,
        total_marks: float,
        correct_count: int,
        incorrect_count: int,
        unanswered_count: int,
        answers: list[dict],
        student_id: int | None = None,
        client_token: str | None = None,
    ) -> MockTestAttempt:
        """
        Persists a graded attempt. If `client_token` is given and this
        exact (mock_test_id, client_token) pair was already recorded -
        a double-click, a browser retry, or the timer's auto-submit racing
        a manual submit - the unique constraint on that pair rejects the
        second insert; we catch it and return the original attempt
        instead of raising, so a duplicate request is harmless rather
        than creating a second graded attempt for the same test session.
        """

        if client_token:
            existing = self.repository.get_by_client_token(db, mock_test_id, client_token)
            if existing is not None:
                return existing

        attempt = MockTestAttempt(
            mock_test_id=mock_test_id,
            student_id=student_id,
            client_token=client_token,
            time_taken_seconds=time_taken_seconds,
            scored_marks=scored_marks,
            total_marks=total_marks,
            correct_count=correct_count,
            incorrect_count=incorrect_count,
            unanswered_count=unanswered_count,
        )
        attempt.answers = [
            MockTestAttemptAnswer(
                question_id=answer["question_id"],
                submitted_answer=answer["submitted_answer"],
                is_correct=answer["is_correct"],
                marks_awarded=answer["marks_awarded"],
            )
            for answer in answers
        ]

        try:
            return self.repository.create(db, attempt)
        except IntegrityError:
            # Lost the race: another request with the same client_token
            # committed between our check above and this insert.
            db.rollback()
            existing = self.repository.get_by_client_token(db, mock_test_id, client_token) if client_token else None
            if existing is None:
                raise
            return existing

    def get_by_student(
        self,
        db: Session,
        student_id: int,
        limit: int = 20
    ) -> list[MockTestAttempt]:
        return self.repository.get_by_student(db, student_id, limit)

    def get_weak_subjects(
        self,
        db: Session,
        student_id: int,
        min_answered: int = 3,
        limit: int = 3
    ) -> list[dict]:
        """
        Subjects where this student's accuracy is lowest, for the
        dashboard's "weak areas" prompt. A subject only qualifies once
        there are at least `min_answered` graded answers for it - below
        that, one lucky or unlucky guess would swing "accuracy" wildly
        and the recommendation would be noise, not signal.
        """
        rows = self.repository.get_subject_accuracy(db, student_id)

        weak_subjects = []
        for subject, correct_count, incorrect_count in rows:
            answered = correct_count + incorrect_count
            if answered < min_answered:
                continue

            weak_subjects.append({
                "subject": subject,
                "accuracy": round(100 * correct_count / answered, 1),
                "answered_count": answered,
            })

        weak_subjects.sort(key=lambda entry: entry["accuracy"])
        return weak_subjects[:limit]

    def get_with_answers(
        self,
        db: Session,
        attempt_id: int
    ) -> MockTestAttempt:

        attempt = self.repository.get_with_answers(db, attempt_id)

        if attempt is None:
            raise NotFoundException("Attempt not found")

        return attempt


class MockTestSessionService(BaseService):
    """
    Owns the server-authoritative "when did this attempt start" clock.
    Nothing about scoring depends on this - it exists purely so the timer
    the student sees, and the time_taken_seconds recorded on the final
    attempt, are both derived from a server timestamp the browser can't
    edit, rather than from localStorage or a client-sent value.
    """

    def __init__(self):
        super().__init__(MockTestSessionRepository())

    def start_or_resume(
        self,
        db: Session,
        mock_test_id: int,
        client_token: str,
        student_id: int | None,
    ) -> MockTestSession:
        existing = self.repository.get_by_client_token(db, mock_test_id, client_token)

        if existing is not None:
            # Same rule as the result page: a session started while logged
            # in belongs to that student only. An anonymous session
            # (student_id is None) has no owner to check.
            if existing.student_id is not None and existing.student_id != student_id:
                raise NotFoundException("Session not found")
            return existing

        session = MockTestSession(
            mock_test_id=mock_test_id,
            student_id=student_id,
            client_token=client_token,
            started_at=datetime.now(timezone.utc),
        )

        try:
            return self.repository.create(db, session)
        except IntegrityError:
            # Lost the race with another request for the same token
            # (e.g. two tabs starting at once) - fetch what actually won.
            db.rollback()
            existing = self.repository.get_by_client_token(db, mock_test_id, client_token)
            if existing is None:
                raise
            return existing

    def get_session_state(
        self,
        db: Session,
        mock_test_id: int,
        client_token: str,
    ) -> tuple[dict[int, str], set[int]]:
        """Persisted answers/marks for restoring an active session - used
        by /start's response so a refresh or reopened tab reconstructs
        the same state the server holds, not whatever localStorage says."""
        session = self.repository.get_with_answers(db, mock_test_id, client_token)
        if session is None:
            return {}, set()

        answers = {
            row.question_id: row.selected_answer
            for row in session.session_answers
            if row.selected_answer
        }
        marked = {row.question_id for row in session.session_answers if row.is_marked}
        return answers, marked

    def save_answer(
        self,
        db: Session,
        mock_test,
        client_token: str,
        student_id: int | None,
        question_id: int,
        answer: str | None,
        marked: bool,
    ) -> None:
        """
        Persists one question's answer/mark within an active session.
        Validates every step server-side - the browser only ever supplies
        which question and which label(s)/value it selected, never
        whether that's correct (this table doesn't even have an
        is_correct column; see MockTestSessionAnswer).
        """
        session = self.repository.get_by_client_token(db, mock_test.id, client_token)
        if session is None:
            raise NotFoundException("Session not found")

        if session.student_id is not None and session.student_id != student_id:
            raise NotFoundException("Session not found")

        if session.submitted_at is not None:
            raise InvalidStateException("This attempt has already been submitted")

        started_at = session.started_at
        if started_at.tzinfo is None:
            # SQLite (dev/tests only) drops tzinfo on round-trip - see the
            # matching fix in mock_test/service.py::start_session.
            started_at = started_at.replace(tzinfo=timezone.utc)

        deadline = started_at + timedelta(seconds=mock_test.duration * 60)
        if datetime.now(timezone.utc) >= deadline:
            raise InvalidStateException("This attempt has expired")

        if not mock_test_question_service.repository.exists_link(db, mock_test.id, question_id):
            raise NotFoundException("Question not found in this mock test")

        question = question_service.repository.get_by_id(db, question_id)
        if question is None:
            raise NotFoundException("Question not found")

        if answer:
            valid_labels = {option.label.upper() for option in question.options}
            submitted_labels = {part.strip().upper() for part in answer.split(",") if part.strip()}
            if valid_labels and not submitted_labels.issubset(valid_labels):
                raise InvalidStateException("Selected option does not belong to this question")

        self.repository.upsert_answer(db, session.id, question_id, answer or None, marked)

    def get_elapsed_seconds(
        self,
        db: Session,
        mock_test_id: int,
        client_token: str | None,
    ) -> int | None:
        """
        Authoritative elapsed time for submission, or None if no session
        was ever started for this token (e.g. a direct API call that
        skipped /start) - the caller decides how to handle that case.
        """
        if not client_token:
            return None

        session = self.repository.get_by_client_token(db, mock_test_id, client_token)
        if session is None:
            return None

        if session.submitted_at is None:
            session.submitted_at = datetime.now(timezone.utc)
            db.commit()

        elapsed = (session.submitted_at - session.started_at).total_seconds()
        return max(0, int(elapsed))


mock_test_session_service = MockTestSessionService()

mock_test_attempt_service = MockTestAttemptService()
