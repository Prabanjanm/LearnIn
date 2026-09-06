from sqlalchemy import case, func
from sqlalchemy.orm import Session, selectinload

from app.common.repositories.base_repository import BaseRepository
from app.modules.paper.model import Paper
from app.modules.question.model import Question
from app.modules.subject.model import Subject

from .model import ConductedTestAttempt, ConductedTestAttemptAnswer


class ConductedTestAttemptRepository(BaseRepository):

    def __init__(self):
        super().__init__(ConductedTestAttempt)

    def get_by_test_and_student(
        self,
        db: Session,
        conducted_test_id: int,
        student_id: int
    ) -> ConductedTestAttempt | None:
        return (
            db.query(ConductedTestAttempt)
            .options(selectinload(ConductedTestAttempt.answers))
            .filter(
                ConductedTestAttempt.conducted_test_id == conducted_test_id,
                ConductedTestAttempt.student_id == student_id,
            )
            .first()
        )

    def get_by_result_code(self, db: Session, result_code: str) -> ConductedTestAttempt | None:
        return (
            db.query(ConductedTestAttempt)
            .options(
                selectinload(ConductedTestAttempt.answers).selectinload(ConductedTestAttemptAnswer.question),
                selectinload(ConductedTestAttempt.conducted_test),
                selectinload(ConductedTestAttempt.student),
            )
            .filter(ConductedTestAttempt.result_code == result_code.strip().upper())
            .first()
        )

    def code_exists(self, db: Session, result_code: str) -> bool:
        return db.query(ConductedTestAttempt).filter(ConductedTestAttempt.result_code == result_code).first() is not None

    def get_by_student(self, db: Session, student_id: int) -> list[ConductedTestAttempt]:
        return (
            db.query(ConductedTestAttempt)
            .options(selectinload(ConductedTestAttempt.conducted_test))
            .filter(ConductedTestAttempt.student_id == student_id)
            .order_by(ConductedTestAttempt.created_at.desc())
            .all()
        )

    def get_by_conducted_test(self, db: Session, conducted_test_id: int) -> list[ConductedTestAttempt]:
        return (
            db.query(ConductedTestAttempt)
            .options(selectinload(ConductedTestAttempt.student))
            .filter(ConductedTestAttempt.conducted_test_id == conducted_test_id)
            .order_by(ConductedTestAttempt.started_at.asc())
            .all()
        )

    def upsert_answer(
        self,
        db: Session,
        attempt_id: int,
        question_id: int,
        selected_answer: str | None,
    ) -> ConductedTestAttemptAnswer:
        existing = (
            db.query(ConductedTestAttemptAnswer)
            .filter(
                ConductedTestAttemptAnswer.attempt_id == attempt_id,
                ConductedTestAttemptAnswer.question_id == question_id,
            )
            .first()
        )

        if existing is not None:
            existing.selected_answer = selected_answer
            db.commit()
            db.refresh(existing)
            return existing

        answer = ConductedTestAttemptAnswer(
            attempt_id=attempt_id,
            question_id=question_id,
            selected_answer=selected_answer,
        )
        return self.create(db, answer)

    def get_subject_breakdown(self, db: Session, attempt_id: int):
        """Per-subject correct/incorrect/score for this one attempt's
        graded answers, for the result report's subject-analysis table."""
        return (
            db.query(
                Subject.name,
                func.sum(case((ConductedTestAttemptAnswer.is_correct.is_(True), 1), else_=0)).label("correct"),
                func.sum(case((ConductedTestAttemptAnswer.is_correct.is_(False), 1), else_=0)).label("incorrect"),
                func.count(ConductedTestAttemptAnswer.id).label("questions"),
                func.sum(ConductedTestAttemptAnswer.marks_awarded).label("score"),
            )
            .join(Question, ConductedTestAttemptAnswer.question_id == Question.id)
            .join(Paper, Question.paper_id == Paper.id)
            .join(Subject, Paper.subject_id == Subject.id)
            .filter(ConductedTestAttemptAnswer.attempt_id == attempt_id)
            .group_by(Subject.id, Subject.name)
            .all()
        )
