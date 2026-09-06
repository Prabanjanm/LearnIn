from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import NotFoundException
from app.common.services.base_service import BaseService
from app.common.utils.file_tracking import cleanup_drive_files, collect_subtree_file_ids
from app.core.enums import StatusEnum

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

        paper = Paper(
            subject_id=data.subject_id,
            title=data.title,
            year=data.year,
            question_file_id=data.question_file_id,
            question_file_mime_type=data.question_file_mime_type,
            question_file_size=data.question_file_file_size,
            question_filename=data.question_filename,
            answer_file_id=data.answer_file_id,
            answer_file_mime_type=data.answer_file_mime_type,
            answer_file_size=data.answer_file_file_size,
            answer_filename=data.answer_filename,
            duration=data.duration,
            total_questions=data.total_questions,
            status=data.status,
        )

        return self.create(db, paper)

    def get_published_by_id(
        self,
        db: Session,
        paper_id: int
    ) -> Paper:

        paper = self.repository.get_published_by_id(db, paper_id)

        if paper is None:
            raise NotFoundException("Paper not found")

        return paper

    def get_published_by_subject(
        self,
        db: Session,
        subject_id: int
    ):
        return self.repository.get_published_by_subject(db, subject_id)

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
        year: int | None = None,
        has_answer_key: bool | None = None,
        term: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ):
        return self.repository.get_filtered(
            db, exam_id, department_id, subject_id, year, has_answer_key, term, page, page_size
        )

    def get_distinct_years(
        self,
        db: Session
    ) -> list[int]:
        return self.repository.get_distinct_years(db)

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

    def update_paper(
        self,
        db: Session,
        paper: Paper,
        data: PaperUpdate
    ) -> Paper:

        updates = data.model_dump(exclude_unset=True)

        # See the comment on PaperCreate.question_file_file_size: the admin
        # CRUD engine's generic key derivation doesn't match these two real
        # column names, so remap them here before applying to the model.
        if "question_file_file_size" in updates:
            updates["question_file_size"] = updates.pop("question_file_file_size")
        if "answer_file_file_size" in updates:
            updates["answer_file_size"] = updates.pop("answer_file_file_size")

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

        stale_file_ids = []
        if replacing_question_file and old_question_file_id:
            stale_file_ids.append(old_question_file_id)
        if replacing_answer_file and old_answer_file_id:
            stale_file_ids.append(old_answer_file_id)

        if stale_file_ids:
            cleanup_drive_files(db, stale_file_ids)

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
