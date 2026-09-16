import uuid
from sqlalchemy.orm import Session, selectinload

from app.common.repositories.base_repository import BaseRepository

from .model import (
    ConductedTestExtractedOption,
    ConductedTestExtractedQuestion,
    ConductedTestPaper,
    ConductedTestPaperJob,
    ConductedTestQuestion,
)


class ConductedTestPaperJobRepository(BaseRepository):

    def __init__(self):
        super().__init__(ConductedTestPaperJob)

    def get_with_questions(self, db: Session, job_id: uuid.UUID) -> ConductedTestPaperJob | None:
        return (
            db.query(ConductedTestPaperJob)
            .options(
                selectinload(ConductedTestPaperJob.extracted_questions)
                .selectinload(ConductedTestExtractedQuestion.options)
            )
            .filter(ConductedTestPaperJob.id == job_id)
            .first()
        )

    def get_for_institution(self, db: Session, job_id: uuid.UUID, institution_id: uuid.UUID) -> ConductedTestPaperJob | None:
        return (
            db.query(ConductedTestPaperJob)
            .options(
                selectinload(ConductedTestPaperJob.extracted_questions)
                .selectinload(ConductedTestExtractedQuestion.options)
            )
            .filter(
                ConductedTestPaperJob.id == job_id,
                ConductedTestPaperJob.institution_id == institution_id,
            )
            .first()
        )

    def list_recent_for_institution(self, db: Session, institution_id: uuid.UUID, limit: int = 100):
        return (
            db.query(ConductedTestPaperJob)
            .filter(ConductedTestPaperJob.institution_id == institution_id)
            .order_by(ConductedTestPaperJob.created_at.desc())
            .limit(limit)
            .all()
        )


class ConductedTestExtractedQuestionRepository(BaseRepository):

    def __init__(self):
        super().__init__(ConductedTestExtractedQuestion)

    def list_for_job(self, db: Session, job_id: uuid.UUID) -> list[ConductedTestExtractedQuestion]:
        return (
            db.query(ConductedTestExtractedQuestion)
            .options(selectinload(ConductedTestExtractedQuestion.options))
            .filter(ConductedTestExtractedQuestion.job_id == job_id)
            .order_by(ConductedTestExtractedQuestion.order_index)
            .all()
        )

    def get_for_job(self, db: Session, job_id: uuid.UUID, question_id: uuid.UUID) -> ConductedTestExtractedQuestion | None:
        return (
            db.query(ConductedTestExtractedQuestion)
            .options(selectinload(ConductedTestExtractedQuestion.options))
            .filter(
                ConductedTestExtractedQuestion.job_id == job_id,
                ConductedTestExtractedQuestion.id == question_id,
            )
            .first()
        )

    def max_order_index(self, db: Session, job_id: uuid.UUID) -> int:
        rows = self.list_for_job(db, job_id)
        return max((q.order_index for q in rows), default=0)


class ConductedTestPaperRepository(BaseRepository):

    def __init__(self):
        super().__init__(ConductedTestPaper)

    def get_for_institution(self, db: Session, paper_id: uuid.UUID, institution_id: uuid.UUID) -> ConductedTestPaper | None:
        return (
            db.query(ConductedTestPaper)
            .filter(
                ConductedTestPaper.id == paper_id,
                ConductedTestPaper.institution_id == institution_id,
            )
            .first()
        )

    def list_for_institution(self, db: Session, institution_id: uuid.UUID) -> list[ConductedTestPaper]:
        return (
            db.query(ConductedTestPaper)
            .filter(ConductedTestPaper.institution_id == institution_id)
            .order_by(ConductedTestPaper.created_at.desc())
            .all()
        )

    def get_questions_for_taking(self, db: Session, conducted_test_paper_id: uuid.UUID) -> list[ConductedTestQuestion]:
        return (
            db.query(ConductedTestQuestion)
            .options(selectinload(ConductedTestQuestion.options))
            .filter(ConductedTestQuestion.conducted_test_paper_id == conducted_test_paper_id)
            .order_by(ConductedTestQuestion.question_number)
            .all()
        )
