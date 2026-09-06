from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import NotFoundException
from app.common.services.base_service import BaseService
from app.core.enums import StatusEnum
from app.modules.question.service import question_service

from .model import MockTest
from .repository import MockTestRepository
from .schema import (
    MockTestCreate,
    MockTestStartResponse,
    MockTestSubmitAnswer,
    MockTestSubmitResponse,
    MockTestSubmitResultItem,
    MockTestUpdate,
)


class MockTestService(BaseService):

    def __init__(self):
        super().__init__(MockTestRepository())

    def get_by_paper(
        self,
        db: Session,
        paper_id: int
    ):
        return self.repository.get_by_paper(db, paper_id)

    def get_published_by_paper(
        self,
        db: Session,
        paper_id: int
    ):
        return self.repository.get_published_by_paper(db, paper_id)

    def get_published_by_id(
        self,
        db: Session,
        mock_test_id: int
    ) -> MockTest:

        mock_test = self.repository.get_published_by_id(db, mock_test_id)

        if mock_test is None:
            raise NotFoundException("Mock test not found")

        return mock_test

    def count_published(
        self,
        db: Session
    ) -> int:
        return self.repository.count_by_status(db, StatusEnum.PUBLISHED)

    def get_recent_published(
        self,
        db: Session,
        limit: int = 6
    ):
        return self.repository.get_recent_published(db, limit)

    def count_published_by_exam(
        self,
        db: Session
    ) -> dict[int, int]:
        return self.repository.count_published_by_exam(db)

    def get_filtered(
        self,
        db: Session,
        exam_id: int | None = None,
        department_id: int | None = None,
        subject_id: int | None = None,
        term: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ):
        return self.repository.get_filtered(db, exam_id, department_id, subject_id, term, page, page_size)

    def get_questions_for_taking(
        self,
        db: Session,
        mock_test_id: int
    ) -> list:
        """
        Ordered question list for a student taking this mock test - the
        mock test itself must be published, but each linked question is
        served regardless of its own status (it was deliberately attached
        to a published test by an admin, so withholding it would just
        break the test).
        """
        from app.modules.mock_test_question.service import mock_test_question_service

        self.get_published_by_id(db, mock_test_id)
        links = mock_test_question_service.get_by_mock_test(db, mock_test_id)
        return [link.question for link in links]

    def start_session(
        self,
        db: Session,
        mock_test_id: int,
        client_token: str,
        student_id: int | None = None,
    ) -> MockTestStartResponse:
        """
        Establishes (or resumes) the server-authoritative clock for one
        attempt. Calling this again with the same client_token - a
        refresh, a second tab sharing the same localStorage - returns the
        original started_at rather than resetting it, so the deadline
        never moves no matter how many times the browser calls this.
        """
        from app.modules.mock_test_attempt.service import mock_test_attempt_service, mock_test_session_service

        mock_test = self.get_published_by_id(db, mock_test_id)
        session = mock_test_session_service.start_or_resume(db, mock_test_id, client_token, student_id)

        deadline = session.started_at + timedelta(seconds=mock_test.duration * 60)
        remaining = max(0, int((deadline - datetime.now(timezone.utc)).total_seconds()))

        attempt_id = None
        if session.submitted_at is not None:
            existing_attempt = mock_test_attempt_service.repository.get_by_client_token(db, mock_test_id, client_token)
            attempt_id = existing_attempt.id if existing_attempt else None

        answers, marked = mock_test_session_service.get_session_state(db, mock_test_id, client_token)

        return MockTestStartResponse(
            client_token=session.client_token,
            duration_seconds=mock_test.duration * 60,
            started_at=session.started_at.isoformat(),
            deadline=deadline.isoformat(),
            remaining_seconds=remaining,
            submitted=session.submitted_at is not None,
            attempt_id=attempt_id,
            answers=answers,
            marked=list(marked),
        )

    def save_answer(
        self,
        db: Session,
        mock_test_id: int,
        client_token: str,
        student_id: int | None,
        question_id: int,
        answer: str,
        marked: bool,
    ) -> None:
        from app.modules.mock_test_attempt.service import mock_test_session_service

        mock_test = self.get_published_by_id(db, mock_test_id)
        mock_test_session_service.save_answer(
            db, mock_test, client_token, student_id, question_id, answer or None, marked
        )

    def submit_attempt(
        self,
        db: Session,
        mock_test_id: int,
        answers: list[MockTestSubmitAnswer],
        student_id: int | None = None,
        client_token: str | None = None,
    ) -> MockTestSubmitResponse:
        """
        Grades a full mock-test submission and persists it as a
        MockTestAttempt so the result is a durable, shareable page rather
        than something that only ever existed in the browser tab that
        submitted it. Scoring is entirely server-side (see
        question_service.evaluate_answer) - the client only ever supplies
        which labels/values it selected per question, never a score, so a
        student can't influence their own result.

        time_taken_seconds is never accepted from the client - it's
        computed from the MockTestSession this client_token started (see
        mock_test_session_service.get_elapsed_seconds), which is the
        server's own clock. A submission with no matching session (e.g. a
        direct API call that skipped /start) simply records no elapsed
        time rather than trusting anything the client claims.

        If `client_token` matches an attempt already recorded for this
        mock test (a duplicate/retried submit of the same test session),
        record_attempt returns that existing row untouched - the response
        below is always built from whatever attempt object comes back, so
        a duplicate request reflects the original graded result rather
        than silently regrading or drifting from what was persisted.

        The `answers` the client posts alongside this request are only a
        fallback (e.g. a direct API call that never used /start or
        /answer). Whenever a MockTestSession exists for this client_token,
        its persisted MockTestSessionAnswer rows are authoritative instead
        - they're what the student actually saved server-side during the
        test, so a stale/edited in-memory answers array from the browser
        can't override what was really recorded.
        """
        from app.modules.mock_test_attempt.service import mock_test_attempt_service, mock_test_session_service

        time_taken_seconds = mock_test_session_service.get_elapsed_seconds(db, mock_test_id, client_token)

        # A session existing at all (even with zero answers saved) means
        # this client_token went through /start, so its persisted answers
        # are authoritative - only fall back to the client-posted answers
        # list when there's no session, i.e. a direct/legacy API call that
        # never used /start or /answer.
        session_exists = bool(client_token) and mock_test_session_service.repository.get_by_client_token(
            db, mock_test_id, client_token
        ) is not None

        if session_exists:
            persisted_answers, _marked = mock_test_session_service.get_session_state(db, mock_test_id, client_token)
            submitted_by_question = persisted_answers
        else:
            submitted_by_question = {a.question_id: a.answer for a in answers}

        questions = self.get_questions_for_taking(db, mock_test_id)

        scored_marks = 0.0
        total_marks = 0.0
        correct_count = 0
        incorrect_count = 0
        unanswered_count = 0
        answer_rows: list[dict] = []

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

            answer_rows.append({
                "question_id": question.id,
                "submitted_answer": submitted,
                "is_correct": is_correct,
                "marks_awarded": marks_awarded,
            })

        attempt = mock_test_attempt_service.record_attempt(
            db,
            mock_test_id=mock_test_id,
            time_taken_seconds=time_taken_seconds,
            scored_marks=scored_marks,
            total_marks=total_marks,
            correct_count=correct_count,
            incorrect_count=incorrect_count,
            unanswered_count=unanswered_count,
            answers=answer_rows,
            student_id=student_id,
            client_token=client_token,
        )

        return MockTestSubmitResponse(
            attempt_id=attempt.id,
            scored_marks=attempt.scored_marks,
            total_marks=attempt.total_marks,
            correct_count=attempt.correct_count,
            incorrect_count=attempt.incorrect_count,
            unanswered_count=attempt.unanswered_count,
            results=[
                MockTestSubmitResultItem(
                    question_id=answer.question_id,
                    is_correct=answer.is_correct,
                    correct_answer=answer.question.correct_answer,
                    explanation=answer.question.explanation,
                    marks_awarded=answer.marks_awarded,
                )
                for answer in attempt.answers
            ],
        )

    def create_mock_test(
        self,
        db: Session,
        data: MockTestCreate
    ) -> MockTest:
        # mock_test_question_service.add_question resyncs total_questions
        # itself after every link it creates, so this starts at 0 rather
        # than trying to precompute it here.
        from app.modules.mock_test_question.schema import MockTestQuestionCreate
        from app.modules.mock_test_question.service import mock_test_question_service

        mock_test = MockTest(
            paper_id=data.paper_id,
            title=data.title,
            description=data.description,
            duration=data.duration,
            total_marks=data.total_marks,
            total_questions=0,
            status=data.status,
        )

        mock_test = self.repository.create(db, mock_test)

        for order, question_id in enumerate(data.question_ids, start=1):
            mock_test_question_service.add_question(
                db,
                MockTestQuestionCreate(
                    mock_test_id=mock_test.id,
                    question_id=question_id,
                    question_order=order,
                ),
            )

        db.refresh(mock_test)
        return mock_test

    def update_mock_test(
        self,
        db: Session,
        mock_test: MockTest,
        data: MockTestUpdate
    ) -> MockTest:

        updates = data.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(mock_test, field, value)

        return self.repository.update(db, mock_test)

    def delete_mock_test(
        self,
        db: Session,
        mock_test: MockTest
    ) -> None:
        self.repository.delete(db, mock_test)


mock_test_service = MockTestService()
