from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import AlreadyExistsException, NotFoundException
from app.common.services.base_service import BaseService
from app.common.utils.file_tracking import cleanup_drive_file, cleanup_drive_files, collect_subtree_file_ids

from .model import Paper
from .repository import PaperRepository
from .schema import PaperCreate, PaperUpdate


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

    def update_paper(
        self,
        db: Session,
        paper: Paper,
        data: PaperUpdate
    ) -> Paper:

        updates = data.model_dump(exclude_unset=True)

        old_question_file_id = paper.question_file_id
        old_answer_file_id = paper.answer_file_id
        replacing_question_file = (
            "question_file_id" in updates and updates["question_file_id"] != old_question_file_id
        )
        replacing_answer_file = (
            "answer_file_id" in updates and updates["answer_file_id"] != old_answer_file_id
        )

        for field, value in updates.items():
            setattr(paper, field, value)

        updated = self.repository.update(db, paper)

        if replacing_question_file:
            cleanup_drive_file(db, old_question_file_id)
        if replacing_answer_file:
            cleanup_drive_file(db, old_answer_file_id)

        return updated

    def delete_paper(
        self,
        db: Session,
        paper: Paper
    ) -> None:
        file_ids = collect_subtree_file_ids(paper)
        self.repository.delete(db, paper)
        cleanup_drive_files(db, file_ids)


paper_service = PaperService()
