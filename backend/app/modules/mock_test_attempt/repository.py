from sqlalchemy import case, func
from sqlalchemy.orm import Session, selectinload

from app.common.repositories.base_repository import BaseRepository
from app.modules.department.model import Department
from app.modules.mock_test.model import MockTest
from app.modules.paper.model import Paper
from app.modules.question.model import Question
from app.modules.subject.model import Subject

from .model import MockTestAttempt, MockTestAttemptAnswer, MockTestSession, MockTestSessionAnswer


class MockTestAttemptRepository(BaseRepository):

    def __init__(self):
        super().__init__(MockTestAttempt)

    def get_by_student(
        self,
        db: Session,
        student_id: int,
        limit: int = 20
    ):
        return (
            db.query(MockTestAttempt)
            .options(
                selectinload(MockTestAttempt.mock_test)
                .selectinload(MockTest.paper)
                .selectinload(Paper.subject)
                .selectinload(Subject.department)
                .selectinload(Department.exam)
            )
            .filter(MockTestAttempt.student_id == student_id)
            .order_by(MockTestAttempt.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_subject_accuracy(
        self,
        db: Session,
        student_id: int
    ):
        """
        Per-subject correct/incorrect counts across every graded answer
        this student has ever submitted, for the dashboard's weak-subject
        recommendation. Unanswered questions are excluded (is_correct is
        NULL) - they're neither a strength nor a weakness signal.
        """
        return (
            db.query(
                Subject,
                func.sum(case((MockTestAttemptAnswer.is_correct.is_(True), 1), else_=0)).label("correct_count"),
                func.sum(case((MockTestAttemptAnswer.is_correct.is_(False), 1), else_=0)).label("incorrect_count"),
            )
            .join(MockTestAttempt, MockTestAttemptAnswer.attempt_id == MockTestAttempt.id)
            .join(Question, MockTestAttemptAnswer.question_id == Question.id)
            .join(Paper, Question.paper_id == Paper.id)
            .join(Subject, Paper.subject_id == Subject.id)
            .filter(
                MockTestAttempt.student_id == student_id,
                MockTestAttemptAnswer.is_correct.is_not(None),
            )
            .group_by(Subject.id)
            .all()
        )

    def get_by_client_token(
        self,
        db: Session,
        mock_test_id: int,
        client_token: str
    ):
        return (
            db.query(MockTestAttempt)
            .filter(
                MockTestAttempt.mock_test_id == mock_test_id,
                MockTestAttempt.client_token == client_token,
            )
            .first()
        )

    def get_with_answers(
        self,
        db: Session,
        attempt_id: int
    ):
        return (
            db.query(MockTestAttempt)
            .options(
                selectinload(MockTestAttempt.mock_test),
                selectinload(MockTestAttempt.answers).selectinload(MockTestAttemptAnswer.question),
            )
            .filter(MockTestAttempt.id == attempt_id)
            .first()
        )


class MockTestSessionRepository(BaseRepository):

    def __init__(self):
        super().__init__(MockTestSession)

    def get_by_client_token(
        self,
        db: Session,
        mock_test_id: int,
        client_token: str
    ):
        return (
            db.query(MockTestSession)
            .filter(
                MockTestSession.mock_test_id == mock_test_id,
                MockTestSession.client_token == client_token,
            )
            .first()
        )

    def get_with_answers(
        self,
        db: Session,
        mock_test_id: int,
        client_token: str
    ):
        return (
            db.query(MockTestSession)
            .options(selectinload(MockTestSession.session_answers))
            .filter(
                MockTestSession.mock_test_id == mock_test_id,
                MockTestSession.client_token == client_token,
            )
            .first()
        )

    def upsert_answer(
        self,
        db: Session,
        session_id: int,
        question_id: int,
        selected_answer: str | None,
        is_marked: bool,
    ) -> MockTestSessionAnswer:
        existing = (
            db.query(MockTestSessionAnswer)
            .filter(
                MockTestSessionAnswer.session_id == session_id,
                MockTestSessionAnswer.question_id == question_id,
            )
            .first()
        )

        if existing is not None:
            existing.selected_answer = selected_answer
            existing.is_marked = is_marked
            db.commit()
            db.refresh(existing)
            return existing

        answer = MockTestSessionAnswer(
            session_id=session_id,
            question_id=question_id,
            selected_answer=selected_answer,
            is_marked=is_marked,
        )
        return self.create(db, answer)
