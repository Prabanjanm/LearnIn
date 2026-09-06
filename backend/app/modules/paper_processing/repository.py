from sqlalchemy.orm import Session, selectinload

from app.common.repositories.base_repository import BaseRepository
from app.modules.department.model import Department
from app.modules.subject.model import Subject

from .model import ExtractedOption, ExtractedQuestion, ExtractedQuestionImage, PaperProcessingJob


class PaperProcessingJobRepository(BaseRepository):

    def __init__(self):
        super().__init__(PaperProcessingJob)

    def list_recent(self, db: Session, limit: int = 100):
        return (
            db.query(PaperProcessingJob)
            .options(
                selectinload(PaperProcessingJob.subject)
                .selectinload(Subject.department)
                .selectinload(Department.exam)
            )
            .order_by(PaperProcessingJob.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_with_questions(self, db: Session, job_id: int):
        return (
            db.query(PaperProcessingJob)
            .options(
                selectinload(PaperProcessingJob.extracted_questions)
                .selectinload(ExtractedQuestion.options),
                selectinload(PaperProcessingJob.extracted_questions)
                .selectinload(ExtractedQuestion.images),
                selectinload(PaperProcessingJob.subject)
                .selectinload(Subject.department)
                .selectinload(Department.exam),
            )
            .filter(PaperProcessingJob.id == job_id)
            .first()
        )

    def count_by_status(self, db: Session, status) -> int:
        return (
            db.query(PaperProcessingJob)
            .filter(PaperProcessingJob.status == status)
            .count()
        )


class ExtractedQuestionRepository(BaseRepository):

    def __init__(self):
        super().__init__(ExtractedQuestion)

    def get_for_job(self, db: Session, job_id: int, question_id: int):
        return (
            db.query(ExtractedQuestion)
            .options(
                selectinload(ExtractedQuestion.options),
                selectinload(ExtractedQuestion.images),
            )
            .filter(
                ExtractedQuestion.id == question_id,
                ExtractedQuestion.job_id == job_id,
            )
            .first()
        )

    def list_for_job(self, db: Session, job_id: int):
        return (
            db.query(ExtractedQuestion)
            .options(
                selectinload(ExtractedQuestion.options),
                selectinload(ExtractedQuestion.images),
            )
            .filter(ExtractedQuestion.job_id == job_id)
            .order_by(ExtractedQuestion.order_index)
            .all()
        )

    def max_order_index(self, db: Session, job_id: int) -> int:
        rows = (
            db.query(ExtractedQuestion.order_index)
            .filter(ExtractedQuestion.job_id == job_id)
            .all()
        )
        return max((row[0] for row in rows), default=0)


class ExtractedOptionRepository(BaseRepository):

    def __init__(self):
        super().__init__(ExtractedOption)


class ExtractedQuestionImageRepository(BaseRepository):

    def __init__(self):
        super().__init__(ExtractedQuestionImage)

    def get_for_question(self, db: Session, question_id: int, image_id: int):
        return (
            db.query(ExtractedQuestionImage)
            .filter(
                ExtractedQuestionImage.id == image_id,
                ExtractedQuestionImage.extracted_question_id == question_id,
            )
            .first()
        )

    def max_order_index(self, db: Session, question_id: int) -> int:
        rows = (
            db.query(ExtractedQuestionImage.order_index)
            .filter(ExtractedQuestionImage.extracted_question_id == question_id)
            .all()
        )
        return max((row[0] for row in rows), default=0)
