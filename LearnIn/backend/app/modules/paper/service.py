from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import AlreadyExistsException, NotFoundException
from app.common.services.base_service import BaseService
from app.modules.subject.model import Subject
from app.modules.temporary_upload.service import mark_temporary_uploads_committed

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

        self.validate_paper_available(db, data.subject_id, data.year)

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

        db.add(paper)
        db.flush()

        file_ids = [data.question_file_id]
        if data.answer_file_id:
            file_ids.append(data.answer_file_id)

        mark_temporary_uploads_committed(db, file_ids, commit=False)
        db.commit()
        db.refresh(paper)
        return paper

    def validate_paper_available(
        self,
        db: Session,
        subject_id: int,
        year: int,
    ) -> None:
        if db.get(Subject, subject_id) is None:
            raise NotFoundException("Subject not found")

        if self.repository.get_by_year(db, subject_id, year):
            raise AlreadyExistsException(
                "A paper already exists for this subject and year"
            )

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
