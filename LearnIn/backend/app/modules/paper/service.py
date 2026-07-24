from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import AlreadyExistsException, NotFoundException
from app.common.services.base_service import BaseService

from .model import Paper
from .repository import PaperRepository
from .schema import PaperCreate


class PaperService(BaseService):

    def __init__(self):
        super().__init__(PaperRepository())

    def create_paper(
        self,
        db: Session,
        data: PaperCreate
    ) -> Paper:

        if self.repository.get_by_year(db, data.subject_id, data.year):
            raise AlreadyExistsException(
                "A paper already exists for this subject and year"
            )

        paper = Paper(
            subject_id=data.subject_id,
            title=data.title,
            year=data.year,
            question_file_id=data.question_file_id,
            question_file_mime_type=data.question_file_mime_type,
            question_file_size=data.question_file_size,
            question_filename=data.question_filename,
            answer_file_id=data.answer_file_id,
            answer_file_mime_type=data.answer_file_mime_type,
            answer_file_size=data.answer_file_size,
            answer_filename=data.answer_filename,
            duration=data.duration,
            status=data.status,
        )

        return self.repository.create(db, paper)

    def get_published_by_subject(
        self,
        db: Session,
        subject_id: int
    ):
        return self.repository.get_published_by_subject(db, subject_id)

    def get_published_by_year(
        self,
        db: Session,
        subject_id: int,
        year: int
    ) -> Paper:

        paper = self.repository.get_published_by_year(db, subject_id, year)

        if paper is None:
            raise NotFoundException("Paper not found")

        return paper

    def get_published_by_id(
        self,
        db: Session,
        paper_id: int
    ) -> Paper:

        paper = self.repository.get_published_by_id(db, paper_id)

        if paper is None:
            raise NotFoundException("Paper not found")

        return paper


paper_service = PaperService()
