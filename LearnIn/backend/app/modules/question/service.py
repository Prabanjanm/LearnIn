from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import NotFoundException
from app.common.services.base_service import BaseService
from app.common.utils.file_tracking import cleanup_drive_file, cleanup_drive_files, collect_subtree_file_ids
from app.core.enums import QuestionType
from app.modules.option.model import Option
from app.modules.paper.repository import PaperRepository

from .model import Question
from .repository import QuestionRepository
from .schema import AnswerCheckResult, QuestionCreate, QuestionUpdate


class QuestionService(BaseService):

    def __init__(self):
        super().__init__(QuestionRepository())
        self._paper_repository = PaperRepository()

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
            options=[
                Option(
                    label=option.label,
                    option_text=option.option_text,
                    image_file_id=option.image_file_id,
                    image_mime_type=option.image_mime_type,
                    image_file_size=option.image_file_size,
                    image_filename=option.image_filename,
                )
                for option in data.options
            ],
            status=data.status,
        )

        created = self.repository.create(db, question)

        paper = self._paper_repository.get_by_id(db, data.paper_id)

        if paper is not None:
            paper.total_questions += 1
            db.commit()

        return created

    def get_published_by_paper(
        self,
        db: Session,
        paper_id: int
    ):
        return self.repository.get_published_by_paper(db, paper_id)

    def get_published_by_id(
        self,
        db: Session,
        question_id: int
    ) -> Question:

        question = self.repository.get_published_by_id(db, question_id)

        if question is None:
            raise NotFoundException("Question not found")

        return question

    def check_answer(
        self,
        db: Session,
        question_id: int,
        submitted_answer: str
    ) -> AnswerCheckResult:

        question = self.get_published_by_id(db, question_id)

        return AnswerCheckResult(
            is_correct=self.is_answer_correct(question, submitted_answer),
            correct_answer=question.correct_answer,
            explanation=question.explanation,
        )

    @staticmethod
    def is_answer_correct(question: Question, submitted_answer: str) -> bool:
        expected = question.correct_answer.strip().upper()
        submitted = submitted_answer.strip().upper()

        if question.question_type == QuestionType.MSQ:
            expected_set = {part.strip() for part in expected.split(",") if part.strip()}
            submitted_set = {part.strip() for part in submitted.split(",") if part.strip()}
            return expected_set == submitted_set

        if question.question_type == QuestionType.NAT:
            try:
                return float(expected) == float(submitted)
            except ValueError:
                return expected == submitted

        return expected == submitted

    def update_question(
        self,
        db: Session,
        question: Question,
        data: QuestionUpdate
    ) -> Question:
        """
        A single commit for scalar fields + (optionally) a full option-set
        replacement, so a failure partway through never leaves some new
        options persisted while others are missing - it's all one flush.
        """

        updates = data.model_dump(exclude_unset=True, exclude={"options"})

        old_image_file_id = question.image_file_id
        old_explanation_image_file_id = question.explanation_image_file_id
        old_option_image_ids = [opt.image_file_id for opt in question.options if opt.image_file_id]

        replacing_image = "image_file_id" in updates and updates["image_file_id"] != old_image_file_id
        replacing_explanation_image = (
            "explanation_image_file_id" in updates
            and updates["explanation_image_file_id"] != old_explanation_image_file_id
        )

        for field, value in updates.items():
            setattr(question, field, value)

        replacing_options = data.options is not None
        if replacing_options:
            try:
                # Flush the deletes before adding the new rows - otherwise a
                # new option can collide with an old one still awaiting
                # deletion under the same (question_id, label) unique constraint.
                question.options = []
                db.flush()

                question.options = [
                    Option(
                        label=option.label,
                        option_text=option.option_text,
                        image_file_id=option.image_file_id,
                        image_mime_type=option.image_mime_type,
                        image_file_size=option.image_file_size,
                        image_filename=option.image_filename,
                    )
                    for option in data.options
                ]
            except Exception:
                db.rollback()
                raise

        try:
            updated = self.repository.update(db, question)
        except Exception:
            db.rollback()
            raise

        if replacing_image:
            cleanup_drive_file(db, old_image_file_id)
        if replacing_explanation_image:
            cleanup_drive_file(db, old_explanation_image_file_id)
        if replacing_options:
            kept_image_ids = {option.image_file_id for option in data.options if option.image_file_id}
            cleanup_drive_files(db, [fid for fid in old_option_image_ids if fid not in kept_image_ids])

        return updated

    def delete_question(
        self,
        db: Session,
        question: Question
    ) -> None:
        file_ids = collect_subtree_file_ids(question)
        paper = self._paper_repository.get_by_id(db, question.paper_id)

        self.repository.delete(db, question)

        if paper is not None and paper.total_questions > 0:
            paper.total_questions -= 1
            db.commit()

        cleanup_drive_files(db, file_ids)


question_service = QuestionService()
