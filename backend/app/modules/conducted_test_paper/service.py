"""
Business logic for an institution's own "upload a paper" conducted-test
flow. Mirrors paper_processing.service's staging/review/publish split
exactly (see that module's docstring for the load-bearing rule): nothing
machine-extracted is ever exposed to a student, real ConductedTestQuestion/
ConductedTestOption rows are only ever created in `publish_job`, and only
after the institution has explicitly reviewed every flagged item.

Every lookup here is institution-scoped (get_job takes institution_id and
404s on a mismatch) - the same multi-tenant pattern already established in
conducted_test/service.py, never trusting the {job_id} in a URL alone.
"""
import logging
import uuid

from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import InvalidStateException, NotFoundException
from app.common.services.base_service import BaseService
from app.core.enums import ExtractionConfidenceEnum, ProcessingStatusEnum, QuestionType, WatermarkStatusEnum

from .model import (
    ConductedTestExtractedOption,
    ConductedTestExtractedQuestion,
    ConductedTestOption,
    ConductedTestPaper,
    ConductedTestPaperJob,
    ConductedTestQuestion,
)
from .repository import (
    ConductedTestExtractedQuestionRepository,
    ConductedTestPaperJobRepository,
    ConductedTestPaperRepository,
)
from .schema import ConductedTestPaperJobCreate, ExtractedQuestionIn

logger = logging.getLogger(__name__)

DEFAULT_QUESTION_TYPE = QuestionType.MCQ
DEFAULT_MARKS = 1.0
DEFAULT_NEGATIVE_MARKS = 0.0

# Question.correct_answer-equivalent NOT NULL sentinel for "no answer key
# supplied" - see paper_processing.service's identical NO_ANSWER_SENTINEL.
NO_ANSWER_SENTINEL = ""

MIN_OPTIONS_TO_PUBLISH = 2

IN_FLIGHT_STATUSES = (
    ProcessingStatusEnum.UPLOADED,
    ProcessingStatusEnum.VALIDATING,
    ProcessingStatusEnum.CLEANING_WATERMARK,
    ProcessingStatusEnum.ANALYZING,
    ProcessingStatusEnum.EXTRACTING,
    ProcessingStatusEnum.DETECTING_QUESTIONS,
)


class ConductedTestPaperJobService(BaseService):

    def __init__(self):
        super().__init__(ConductedTestPaperJobRepository())
        self._questions = ConductedTestExtractedQuestionRepository()

    # ------------------------------------------------------------ lookup --

    def get_job(self, db: Session, job_id: uuid.UUID, institution_id: uuid.UUID | None = None) -> ConductedTestPaperJob:
        """`institution_id` is optional only so background.py (which
        already trusts the job_id it was given) can fetch without it -
        every institution-facing caller (router.py/pages.py) must always
        pass it."""
        job = (
            self.repository.get_for_institution(db, job_id, institution_id)
            if institution_id is not None
            else self.repository.get_with_questions(db, job_id)
        )

        if job is None:
            raise NotFoundException("Processing job not found")

        return job

    def list_jobs(self, db: Session, institution_id: uuid.UUID):
        return self.repository.list_recent_for_institution(db, institution_id)

    def list_questions(self, db: Session, job_id: uuid.UUID):
        return self._questions.list_for_job(db, job_id)

    # ------------------------------------------------------------ create --

    def create_job(
        self,
        db: Session,
        institution_id: uuid.UUID,
        created_by_institution_user_id: int,
        data: ConductedTestPaperJobCreate,
    ) -> ConductedTestPaperJob:
        job = ConductedTestPaperJob(
            institution_id=institution_id,
            created_by_institution_user_id=created_by_institution_user_id,
            title=data.title,
            original_file_id=data.original_file_id,
            original_mime_type=data.original_mime_type,
            original_file_size=data.original_file_size,
            original_filename=data.original_filename,
            status=ProcessingStatusEnum.UPLOADED,
            watermark_status=WatermarkStatusEnum.NOT_NEEDED,
            ocr_used=False,
        )
        return self.repository.create(db, job)

    # ------------------------------------------------------- pipeline io --

    def set_status(
        self,
        db: Session,
        job: ConductedTestPaperJob,
        status: ProcessingStatusEnum,
        error_message: str | None = None,
    ) -> ConductedTestPaperJob:
        job.status = status
        job.error_message = error_message
        db.commit()
        db.refresh(job)
        return job

    def fail_job(
        self,
        db: Session,
        job: ConductedTestPaperJob,
        message: str,
        status: ProcessingStatusEnum = ProcessingStatusEnum.FAILED,
    ) -> ConductedTestPaperJob:
        return self.set_status(db, job, status, message)

    def request_cancel(self, db: Session, job_id: uuid.UUID, institution_id: uuid.UUID) -> ConductedTestPaperJob:
        job = self.get_job(db, job_id, institution_id)

        if job.status not in IN_FLIGHT_STATUSES:
            raise InvalidStateException("This job is not currently running.")

        job.cancel_requested = True
        db.commit()
        db.refresh(job)

        return job

    def is_cancel_requested(self, db: Session, job: ConductedTestPaperJob) -> bool:
        db.refresh(job, attribute_names=["cancel_requested"])
        return job.cancel_requested

    def replace_extracted_questions(
        self,
        db: Session,
        job: ConductedTestPaperJob,
        parsed_questions,
        ocr_used: bool,
    ) -> None:
        job.extracted_questions.clear()
        db.flush()

        for index, parsed in enumerate(parsed_questions, start=1):
            job.extracted_questions.append(ConductedTestExtractedQuestion(
                order_index=index,
                question_number=parsed.question_number,
                question_text=parsed.question_text,
                raw_source_text=parsed.raw_source_text,
                confidence=parsed.confidence,
                needs_review=parsed.needs_review,
                correct_answer=None,
                options=[
                    ConductedTestExtractedOption(label=option.label, option_text=option.option_text)
                    for option in parsed.options
                ],
            ))

        job.ocr_used = ocr_used
        db.flush()
        self.resync_counters(db, job)

    def resync_counters(self, db: Session, job: ConductedTestPaperJob) -> None:
        questions = self._questions.list_for_job(db, job.id)

        job.questions_extracted = len(questions)
        job.questions_low_confidence = sum(
            1 for question in questions if question.confidence == ExtractionConfidenceEnum.LOW
        )

        db.commit()
        db.refresh(job)

    # -------------------------------------------------------- review edit --

    def _editable_job(self, db: Session, job_id: uuid.UUID, institution_id: uuid.UUID) -> ConductedTestPaperJob:
        job = self.get_job(db, job_id, institution_id)

        if job.status == ProcessingStatusEnum.PUBLISHED:
            raise InvalidStateException(
                "This paper has already been confirmed and can no longer be edited."
            )

        return job

    def get_question(self, db: Session, job_id: uuid.UUID, question_id: uuid.UUID) -> ConductedTestExtractedQuestion:
        question = self._questions.get_for_job(db, job_id, question_id)

        if question is None:
            raise NotFoundException("Extracted question not found for this job")

        return question

    def update_question(
        self,
        db: Session,
        job_id: uuid.UUID,
        institution_id: uuid.UUID,
        question_id: uuid.UUID,
        data: ExtractedQuestionIn,
    ) -> ConductedTestExtractedQuestion:
        job = self._editable_job(db, job_id, institution_id)
        question = self.get_question(db, job_id, question_id)

        question.question_text = data.question_text.strip()
        question.question_number = data.question_number

        answer = (data.correct_answer or "").strip()
        question.correct_answer = answer or None

        if data.needs_review is not None:
            question.needs_review = data.needs_review

        question.options.clear()
        db.flush()

        for option in data.options:
            text = option.option_text.strip()
            if not text:
                continue
            question.options.append(ConductedTestExtractedOption(
                label=option.label.strip().upper()[:2],
                option_text=text,
            ))

        db.commit()
        db.refresh(question)
        self.resync_counters(db, job)

        return question

    def set_needs_review(
        self,
        db: Session,
        job_id: uuid.UUID,
        institution_id: uuid.UUID,
        question_id: uuid.UUID,
        needs_review: bool,
    ) -> ConductedTestExtractedQuestion:
        self._editable_job(db, job_id, institution_id)
        question = self.get_question(db, job_id, question_id)

        question.needs_review = needs_review
        db.commit()
        db.refresh(question)

        return question

    def add_question(
        self,
        db: Session,
        job_id: uuid.UUID,
        institution_id: uuid.UUID,
        data: ExtractedQuestionIn,
    ) -> ConductedTestExtractedQuestion:
        job = self._editable_job(db, job_id, institution_id)

        answer = (data.correct_answer or "").strip()

        question = ConductedTestExtractedQuestion(
            job_id=job.id,
            order_index=self._questions.max_order_index(db, job.id) + 1,
            question_number=data.question_number,
            question_text=data.question_text.strip(),
            raw_source_text=None,
            confidence=ExtractionConfidenceEnum.HIGH,
            needs_review=bool(data.needs_review),
            correct_answer=answer or None,
            options=[
                ConductedTestExtractedOption(
                    label=option.label.strip().upper()[:2],
                    option_text=option.option_text.strip(),
                )
                for option in data.options
                if option.option_text.strip()
            ],
        )

        db.add(question)
        db.commit()
        db.refresh(question)
        self.resync_counters(db, job)

        return question

    def delete_question(self, db: Session, job_id: uuid.UUID, institution_id: uuid.UUID, question_id: uuid.UUID) -> None:
        job = self._editable_job(db, job_id, institution_id)
        question = self.get_question(db, job_id, question_id)

        db.delete(question)
        db.flush()

        self._renumber(db, job)
        db.commit()
        self.resync_counters(db, job)

    def move_question(self, db: Session, job_id: uuid.UUID, institution_id: uuid.UUID, question_id: uuid.UUID, direction: str) -> None:
        job = self._editable_job(db, job_id, institution_id)
        questions = self._questions.list_for_job(db, job_id)

        index = next((i for i, q in enumerate(questions) if q.id == question_id), None)
        if index is None:
            raise NotFoundException("Extracted question not found for this job")

        target = index - 1 if direction == "up" else index + 1
        if target < 0 or target >= len(questions):
            return

        questions[index], questions[target] = questions[target], questions[index]
        self._apply_order(db, questions)
        db.commit()

    def _renumber(self, db: Session, job: ConductedTestPaperJob) -> None:
        self._apply_order(db, self._questions.list_for_job(db, job.id))

    def _apply_order(self, db: Session, questions: list[ConductedTestExtractedQuestion]) -> None:
        for offset, question in enumerate(questions, start=1):
            question.order_index = -offset
        db.flush()

        for offset, question in enumerate(questions, start=1):
            question.order_index = offset
        db.flush()

    # ------------------------------------------------------------ review --

    def mark_reviewed(self, db: Session, job_id: uuid.UUID, institution_id: uuid.UUID) -> ConductedTestPaperJob:
        job = self._editable_job(db, job_id, institution_id)

        if not job.extracted_questions:
            raise InvalidStateException(
                "There are no questions to save. Add at least one question first."
            )

        job.status = ProcessingStatusEnum.REVIEWED
        job.error_message = None
        db.commit()
        db.refresh(job)

        return job

    # ----------------------------------------------------------- publish --

    def publish_blockers(self, db: Session, job: ConductedTestPaperJob) -> list[str]:
        blockers: list[str] = []

        if not job.title or not job.title.strip():
            blockers.append("A title is required.")

        questions = self._questions.list_for_job(db, job.id)

        if not questions:
            blockers.append("At least one question is required.")

        for question in questions:
            if not question.question_text or not question.question_text.strip():
                blockers.append(f"Question {question.order_index} has no text.")
            if len(question.options) < MIN_OPTIONS_TO_PUBLISH:
                blockers.append(
                    f"Question {question.order_index} has fewer than {MIN_OPTIONS_TO_PUBLISH} options."
                )

        flagged = [q.order_index for q in questions if q.needs_review]
        if flagged:
            blockers.append(
                "These questions are still marked for review: "
                + ", ".join(str(index) for index in flagged)
                + ". Clear each one before confirming."
            )

        return blockers

    def publish_job(self, db: Session, job_id: uuid.UUID, institution_id: uuid.UUID) -> ConductedTestPaper:
        job = self.get_job(db, job_id, institution_id)

        if job.status == ProcessingStatusEnum.PUBLISHED:
            raise InvalidStateException("This paper has already been confirmed.")

        blockers = self.publish_blockers(db, job)
        if blockers:
            raise InvalidStateException(" ".join(blockers))

        conducted_test_paper = ConductedTestPaper(
            institution_id=job.institution_id,
            created_by_institution_user_id=job.created_by_institution_user_id,
            title=job.title,
            question_file_id=job.effective_source_file_id,
            question_file_mime_type=job.cleaned_mime_type or job.original_mime_type,
            question_file_size=job.cleaned_file_size or job.original_file_size,
            question_filename=job.cleaned_filename or job.original_filename,
        )
        db.add(conducted_test_paper)
        db.flush()

        questions = self._questions.list_for_job(db, job.id)

        for question in questions:
            db.add(ConductedTestQuestion(
                conducted_test_paper_id=conducted_test_paper.id,
                question_number=question.order_index,
                question_type=DEFAULT_QUESTION_TYPE,
                question_text=question.question_text,
                correct_answer=(question.correct_answer or NO_ANSWER_SENTINEL),
                marks=DEFAULT_MARKS,
                negative_marks=DEFAULT_NEGATIVE_MARKS,
                options=[
                    ConductedTestOption(label=option.label, option_text=option.option_text)
                    for option in question.options
                ],
            ))

        conducted_test_paper.total_questions = len(questions)

        job.conducted_test_paper_id = conducted_test_paper.id
        job.status = ProcessingStatusEnum.PUBLISHED
        job.error_message = None

        db.commit()
        db.refresh(conducted_test_paper)

        return conducted_test_paper


class ConductedTestPaperService(BaseService):
    """Read-side access to confirmed papers - used by conducted_test/
    service.py's "pick one of my own uploaded papers" path."""

    def __init__(self):
        super().__init__(ConductedTestPaperRepository())

    def get_for_institution(self, db: Session, paper_id: uuid.UUID, institution_id: uuid.UUID) -> ConductedTestPaper:
        paper = self.repository.get_for_institution(db, paper_id, institution_id)
        if paper is None:
            raise NotFoundException("Conducted test paper not found")
        return paper

    def list_for_institution(self, db: Session, institution_id: uuid.UUID) -> list[ConductedTestPaper]:
        return self.repository.list_for_institution(db, institution_id)

    def get_questions_for_taking(self, db: Session, conducted_test_paper_id: uuid.UUID) -> list[ConductedTestQuestion]:
        return self.repository.get_questions_for_taking(db, conducted_test_paper_id)


conducted_test_paper_job_service = ConductedTestPaperJobService()
conducted_test_paper_service = ConductedTestPaperService()
