import secrets
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import ForbiddenException, InvalidStateException, NotFoundException
from app.common.services.base_service import BaseService
from app.core.enums import ConductedTestAttemptStatus, StatusEnum, TerminationReason
from app.modules.conducted_test.model import ConductedTest
from app.modules.conducted_test.service import conducted_test_service
from app.modules.mock_test.service import mock_test_service
from app.modules.question.service import question_service
from app.modules.student.model import Student

from .model import ConductedTestAttempt
from .repository import ConductedTestAttemptRepository

_RESULT_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_RESULT_CODE_LENGTH = 8

_TERMINAL_STATUSES = {
    ConductedTestAttemptStatus.SUBMITTED,
    ConductedTestAttemptStatus.AUTO_SUBMITTED,
    ConductedTestAttemptStatus.TERMINATED,
}


class ConductedTestAttemptService(BaseService):

    def __init__(self):
        super().__init__(ConductedTestAttemptRepository())

    # ----------------------------------------------------------- join --

    def join_for_instructions(self, db: Session, test_code: str, student: Student) -> dict:
        conducted_test = conducted_test_service.get_by_code_for_join(db, test_code)
        _start, end = conducted_test_service.window(conducted_test)

        existing = self.repository.get_by_test_and_student(db, conducted_test.id, student.id)

        return {
            "conducted_test": conducted_test,
            "window_ends_at": end,
            "already_completed": existing is not None and existing.status in _TERMINAL_STATUSES,
        }

    def start_or_resume(self, db: Session, conducted_test_id: int, student: Student) -> dict:
        conducted_test = conducted_test_service.get_or_404(db, conducted_test_id, "Conducted test not found")
        if conducted_test.status != StatusEnum.PUBLISHED:
            raise NotFoundException("This test is not currently active")

        start, end = conducted_test_service.window(conducted_test)
        now = datetime.now(timezone.utc)

        if now < start:
            raise InvalidStateException("This test has not started yet")
        if now >= end:
            raise InvalidStateException("This test's scheduled window has closed")

        attempt = self.repository.get_by_test_and_student(db, conducted_test.id, student.id)

        if attempt is None:
            attempt = ConductedTestAttempt(
                conducted_test_id=conducted_test.id,
                student_id=student.id,
                result_code=self._generate_unique_result_code(db),
                status=ConductedTestAttemptStatus.IN_PROGRESS,
                started_at=now,
            )
            try:
                attempt = self.repository.create(db, attempt)
            except IntegrityError:
                db.rollback()
                attempt = self.repository.get_by_test_and_student(db, conducted_test.id, student.id)
                if attempt is None:
                    raise

        if attempt.status in _TERMINAL_STATUSES:
            raise ForbiddenException("You have already completed this test - only one attempt is allowed")

        # Lazy expiry safety net: even if the student's browser never calls
        # /submit after the window closes, the backend finalizes the attempt
        # itself the next time it's touched, so an abandoned attempt can
        # never be silently resumed or left open past the real deadline.
        if now >= end:
            attempt = self._finalize(db, attempt, TerminationReason.TIME_EXPIRED)
            raise InvalidStateException("This test's scheduled window has closed")

        questions = mock_test_service.get_questions_for_taking(db, conducted_test.mock_test_id)
        answers = {a.question_id: a.selected_answer for a in attempt.answers if a.selected_answer}

        return {
            "attempt": attempt,
            "remaining_seconds": max(0, int((end - now).total_seconds())),
            "window_ends_at": end,
            "questions": questions,
            "answers": answers,
        }

    # --------------------------------------------------------- answer --

    def save_answer(
        self,
        db: Session,
        conducted_test_id: int,
        student: Student,
        question_id: int,
        answer: str | None,
    ) -> None:
        conducted_test = conducted_test_service.get_or_404(db, conducted_test_id, "Conducted test not found")
        attempt = self.repository.get_by_test_and_student(db, conducted_test.id, student.id)

        if attempt is None:
            raise NotFoundException("No active attempt found - start the test first")

        _start, end = conducted_test_service.window(conducted_test)
        now = datetime.now(timezone.utc)

        if now >= end and attempt.status == ConductedTestAttemptStatus.IN_PROGRESS:
            self._finalize(db, attempt, TerminationReason.TIME_EXPIRED)
            raise InvalidStateException("This test's scheduled window has closed")

        if attempt.status != ConductedTestAttemptStatus.IN_PROGRESS:
            raise InvalidStateException("This attempt has already been finalized")

        questions = mock_test_service.get_questions_for_taking(db, conducted_test.mock_test_id)
        question = next((q for q in questions if q.id == question_id), None)
        if question is None:
            raise NotFoundException("Question not found in this test")

        if answer:
            valid_labels = {option.label.upper() for option in question.options}
            submitted_labels = {part.strip().upper() for part in answer.split(",") if part.strip()}
            if valid_labels and not submitted_labels.issubset(valid_labels):
                raise InvalidStateException("Selected option does not belong to this question")

        self.repository.upsert_answer(db, attempt.id, question_id, answer or None)

    # -------------------------------------------------------- finalize --

    def submit(self, db: Session, conducted_test_id: int, student: Student) -> ConductedTestAttempt:
        """Manual submit or a client-detected time-expiry - the server
        never trusts which one the client claims; it decides purely from
        whether the real scheduled window has already closed."""
        conducted_test = conducted_test_service.get_or_404(db, conducted_test_id, "Conducted test not found")
        attempt = self.repository.get_by_test_and_student(db, conducted_test.id, student.id)

        if attempt is None:
            raise NotFoundException("No active attempt found")

        if attempt.status in _TERMINAL_STATUSES:
            # Idempotent: a manual submit racing an auto-submit (tab-switch,
            # timer) must not error - both just return the one real result.
            return attempt

        _start, end = conducted_test_service.window(conducted_test)
        reason = TerminationReason.TIME_EXPIRED if datetime.now(timezone.utc) >= end else TerminationReason.MANUAL_SUBMIT
        return self._finalize(db, attempt, reason)

    def record_violation(
        self,
        db: Session,
        conducted_test_id: int,
        student: Student,
        reason: TerminationReason,
    ) -> ConductedTestAttempt:
        """Tab-switch / fullscreen-exit: the frontend calls this the
        moment it detects the violation, with whatever answers were saved
        up to that point (already persisted via /answer) - this call only
        needs to lock the attempt, not resend every answer."""
        conducted_test = conducted_test_service.get_or_404(db, conducted_test_id, "Conducted test not found")
        attempt = self.repository.get_by_test_and_student(db, conducted_test.id, student.id)

        if attempt is None:
            raise NotFoundException("No active attempt found")

        if attempt.status in _TERMINAL_STATUSES:
            return attempt

        return self._finalize(db, attempt, reason)

    def terminate_attempt(self, db: Session, conducted_test: ConductedTest, student_id: int) -> ConductedTestAttempt:
        """Called only after the institution's ownership of `conducted_test`
        has already been verified upstream (see
        conducted_test_service.get_for_manage) - this method itself does
        not re-check institution scoping, since it only ever operates on
        an already-scoped ConductedTest object, never a bare id."""
        attempt = self.repository.get_by_test_and_student(db, conducted_test.id, student_id)
        if attempt is None:
            raise NotFoundException("No attempt found for this student")

        if attempt.status in _TERMINAL_STATUSES:
            return attempt

        return self._finalize(db, attempt, TerminationReason.ADMIN_TERMINATED)

    def _finalize(self, db: Session, attempt: ConductedTestAttempt, reason: TerminationReason) -> ConductedTestAttempt:
        now = datetime.now(timezone.utc)
        questions = mock_test_service.get_questions_for_taking(db, attempt.conducted_test.mock_test_id)
        submitted_by_question = {a.question_id: a.selected_answer for a in attempt.answers}

        scored_marks = 0.0
        total_marks = 0.0
        correct_count = 0
        incorrect_count = 0
        unanswered_count = 0
        graded_by_question: dict[int, tuple[bool | None, float]] = {}

        for question in questions:
            total_marks += question.marks
            submitted = submitted_by_question.get(question.id)
            is_correct, marks_awarded = question_service.evaluate_answer(question, submitted)

            if is_correct is None:
                unanswered_count += 1
            elif is_correct:
                correct_count += 1
            else:
                incorrect_count += 1

            scored_marks += marks_awarded
            graded_by_question[question.id] = (is_correct, marks_awarded)

        for answer in attempt.answers:
            is_correct, marks_awarded = graded_by_question.get(answer.question_id, (None, 0.0))
            answer.is_correct = is_correct
            answer.marks_awarded = marks_awarded

        attempt.status = (
            ConductedTestAttemptStatus.TERMINATED
            if reason == TerminationReason.ADMIN_TERMINATED
            else ConductedTestAttemptStatus.SUBMITTED
            if reason == TerminationReason.MANUAL_SUBMIT
            else ConductedTestAttemptStatus.AUTO_SUBMITTED
        )
        attempt.termination_reason = reason
        attempt.submitted_at = now
        started_at = attempt.started_at
        if started_at.tzinfo is None:
            # SQLite (tests only) drops tzinfo on round-trip - see
            # conducted_test/service.py::window for the same fix.
            started_at = started_at.replace(tzinfo=timezone.utc)
        attempt.time_taken_seconds = max(0, int((now - started_at).total_seconds()))
        attempt.scored_marks = scored_marks
        attempt.total_marks = total_marks
        attempt.correct_count = correct_count
        attempt.incorrect_count = incorrect_count
        attempt.unanswered_count = unanswered_count

        return self.repository.update(db, attempt)

    # ---------------------------------------------------------- results --

    def get_result_for_student(self, db: Session, result_code: str, student: Student) -> dict:
        attempt = self.repository.get_by_result_code(db, result_code)
        if attempt is None:
            raise NotFoundException("Result not found")
        if attempt.student_id != student.id:
            raise ForbiddenException("You are not authorized to view this result")
        return self._build_report(db, attempt)

    def get_result_for_institution(self, db: Session, result_code: str, institution_id: int) -> dict:
        attempt = self.repository.get_by_result_code(db, result_code)
        if attempt is None:
            raise NotFoundException("Result not found")
        if attempt.conducted_test.institution_id != institution_id:
            raise ForbiddenException("You are not authorized to view this result")
        return self._build_report(db, attempt)

    def get_my_results(self, db: Session, student: Student) -> list[ConductedTestAttempt]:
        return self.repository.get_by_student(db, student.id)

    def get_participants(self, db: Session, conducted_test: ConductedTest) -> list[dict]:
        attempts = self.repository.get_by_conducted_test(db, conducted_test.id)
        return [
            {
                "student_id": attempt.student_id,
                "student_name": attempt.student.full_name,
                "student_email": attempt.student.email,
                "result_code": attempt.result_code,
                "status": attempt.status.value,
                "termination_reason": attempt.termination_reason.value if attempt.termination_reason else None,
                "started_at": attempt.started_at,
                "submitted_at": attempt.submitted_at,
                "scored_marks": attempt.scored_marks,
                "total_marks": attempt.total_marks,
                "percentage": _percentage(attempt.scored_marks, attempt.total_marks),
            }
            for attempt in attempts
        ]

    def _build_report(self, db: Session, attempt: ConductedTestAttempt) -> dict:
        breakdown = self.repository.get_subject_breakdown(db, attempt.id)
        attempted = attempt.correct_count + attempt.incorrect_count if attempt.correct_count is not None else 0

        return {
            "result_code": attempt.result_code,
            "test_title": attempt.conducted_test.title,
            "student_name": attempt.student.full_name,
            "student_email": attempt.student.email,
            "started_at": attempt.started_at,
            "submitted_at": attempt.submitted_at,
            "duration_minutes": attempt.conducted_test.duration_minutes,
            "time_taken_seconds": attempt.time_taken_seconds,
            "total_questions": len(attempt.answers),
            "attempted": attempted,
            "correct_count": attempt.correct_count or 0,
            "incorrect_count": attempt.incorrect_count or 0,
            "unanswered_count": attempt.unanswered_count or 0,
            "scored_marks": attempt.scored_marks or 0.0,
            "total_marks": attempt.total_marks or 0.0,
            "percentage": _percentage(attempt.scored_marks, attempt.total_marks),
            "status": attempt.status.value,
            "termination_reason": attempt.termination_reason.value if attempt.termination_reason else None,
            "subject_breakdown": [
                {
                    "subject": name,
                    "questions": int(questions),
                    "correct": int(correct),
                    "incorrect": int(incorrect),
                    "accuracy": round(100 * correct / (correct + incorrect), 1) if (correct + incorrect) else None,
                    "score": float(score or 0.0),
                }
                for name, correct, incorrect, questions, score in breakdown
            ],
        }

    def _generate_unique_result_code(self, db: Session) -> str:
        for _ in range(20):
            candidate = "LIN-R" + "".join(secrets.choice(_RESULT_CODE_ALPHABET) for _ in range(_RESULT_CODE_LENGTH))
            if not self.repository.code_exists(db, candidate):
                return candidate
        raise InvalidStateException("Could not generate a unique result id, please try again")


def _percentage(scored: float | None, total: float | None) -> float | None:
    if not total:
        return None
    return round(100 * max(0.0, scored or 0.0) / total, 1)


conducted_test_attempt_service = ConductedTestAttemptService()
