from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import NotFoundException
from app.common.services.base_service import BaseService
from app.common.utils.file_tracking import cleanup_drive_file
from app.core.enums import QuestionType, StatusEnum
from app.modules.option.model import Option

from .model import Question
from .repository import QuestionRepository
from .schema import OptionIn, QuestionCreate, QuestionUpdate


class QuestionService(BaseService):

    def __init__(self):
        super().__init__(QuestionRepository())

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

    def count_published(
        self,
        db: Session
    ) -> int:
        return self.repository.count_by_status(db, StatusEnum.PUBLISHED)

    def get_published_by_id(
        self,
        db: Session,
        question_id: int
    ) -> Question:

        question = self.repository.get_published_by_id(db, question_id)

        if question is None:
            raise NotFoundException("Question not found")

        return question

    def evaluate_answer(
        self,
        question: Question,
        submitted: str | None
    ) -> tuple[bool | None, float]:
        """
        Grades one submitted answer against the question's correct_answer.
        This is the single source of truth for scoring - used by both the
        practice page's instant "check answer" and mock-test submission -
        so a student can never influence their own score from the client.

        Returns (is_correct, marks_awarded). is_correct is None when
        nothing was submitted (no credit, no penalty). For MCQ/MSQ, the
        submitted labels are compared as an unordered set so "A,C" and
        "C,A" are equivalent; NAT answers are compared as trimmed strings.
        """
        if submitted is None or not submitted.strip():
            return None, 0.0

        if question.question_type == QuestionType.NAT:
            is_correct = submitted.strip() == question.correct_answer.strip()
        else:
            correct_labels = {part.strip().upper() for part in question.correct_answer.split(",") if part.strip()}
            submitted_labels = {part.strip().upper() for part in submitted.split(",") if part.strip()}
            is_correct = submitted_labels == correct_labels

        marks_awarded = question.marks if is_correct else -question.negative_marks
        return is_correct, marks_awarded

    def create_question(
        self,
        db: Session,
        data: QuestionCreate
    ) -> Question:

        question = Question(
            paper_id=data.paper_id,
            question_number=data.question_number,
            question_type=data.question_type,
            question_text=data.question_text,
            image_file_id=data.image_file_id,
            image_mime_type=data.image_mime_type,
            image_file_size=data.image_file_size,
            image_filename=data.image_filename,
            correct_answer=data.correct_answer,
            explanation=data.explanation,
            explanation_image_file_id=data.explanation_image_file_id,
            explanation_image_mime_type=data.explanation_image_mime_type,
            explanation_image_file_size=data.explanation_image_file_size,
            explanation_image_filename=data.explanation_image_filename,
            marks=data.marks,
            negative_marks=data.negative_marks,
            difficulty=data.difficulty,
            status=data.status,
        )

        question.options = [
            self._build_option(option) for option in data.options
        ]

        created = self.repository.create(db, question)
        self._resync_paper_total_questions(db, data.paper_id)
        return created

    def update_question(
        self,
        db: Session,
        question: Question,
        data: QuestionUpdate
    ) -> Question:

        updates = data.model_dump(exclude_unset=True, exclude={"options"})

        old_image_file_id = question.image_file_id
        old_explanation_image_file_id = question.explanation_image_file_id

        replacing_image = "image_file_id" in updates and updates["image_file_id"] != old_image_file_id
        replacing_explanation_image = (
            "explanation_image_file_id" in updates
            and updates["explanation_image_file_id"] != old_explanation_image_file_id
        )

        for field, value in updates.items():
            setattr(question, field, value)

        stale_option_image_ids: list[str] = []
        if data.options is not None:
            stale_option_image_ids = self._sync_options(question, data.options)

        updated = self.repository.update(db, question)

        if replacing_image:
            cleanup_drive_file(db, old_image_file_id)
        if replacing_explanation_image:
            cleanup_drive_file(db, old_explanation_image_file_id)
        for file_id in stale_option_image_ids:
            cleanup_drive_file(db, file_id)

        return updated

    def delete_question(
        self,
        db: Session,
        question: Question
    ) -> None:
        file_ids = [question.image_file_id, question.explanation_image_file_id]
        file_ids.extend(option.image_file_id for option in question.options)
        paper_id = question.paper_id

        self.repository.delete(db, question)
        self._resync_paper_total_questions(db, paper_id)

        for file_id in file_ids:
            cleanup_drive_file(db, file_id)

    def _resync_paper_total_questions(self, db: Session, paper_id: int) -> None:
        """Keeps Paper.total_questions (shown on the public paper page) in
        sync with how many questions actually exist for it - the same
        pattern mock_test_question_service uses for MockTest.total_questions."""
        from app.modules.paper.repository import PaperRepository

        paper = PaperRepository().get_by_id(db, paper_id)
        if paper is not None:
            paper.total_questions = len(self.repository.get_by_paper(db, paper_id))
            db.commit()

    def _build_option(self, option: OptionIn) -> Option:
        return Option(
            label=option.label,
            option_text=option.option_text,
            image_file_id=option.image_file_id,
            image_mime_type=option.image_mime_type,
            image_file_size=option.image_file_size,
            image_filename=option.image_filename,
        )

    def _sync_options(self, question: Question, options: list[OptionIn]) -> list[str]:
        """
        Full replace of the question's options from the submitted list,
        matched by label: existing rows are updated in place (so their id
        is preserved), labels no longer present are dropped (cascade delete
        via the `options` relationship), and new labels are appended.
        Returns the image_file_ids that were replaced or dropped, for the
        caller to clean up from Drive after the DB commit.
        """
        existing_by_label = {option.label: option for option in question.options}
        submitted_labels = {option.label for option in options}

        stale_image_ids: list[str] = []

        for label, existing in existing_by_label.items():
            if label not in submitted_labels and existing.image_file_id:
                stale_image_ids.append(existing.image_file_id)

        synced_options: list[Option] = []
        for option in options:
            existing = existing_by_label.get(option.label)
            if existing is not None:
                if existing.image_file_id and existing.image_file_id != option.image_file_id:
                    stale_image_ids.append(existing.image_file_id)

                existing.option_text = option.option_text
                existing.image_file_id = option.image_file_id
                existing.image_mime_type = option.image_mime_type
                existing.image_file_size = option.image_file_size
                existing.image_filename = option.image_filename
                synced_options.append(existing)
            else:
                synced_options.append(self._build_option(option))

        question.options = synced_options
        return stale_image_ids


question_service = QuestionService()
