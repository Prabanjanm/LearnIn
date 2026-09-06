"""
Business logic for the Question Paper Processing workflow.

The load-bearing rule enforced here: `ExtractedQuestion`/`ExtractedOption`
are a staging area. Real `Question`/`Option` rows are created in exactly one
place - `publish_job` - and only after an explicit admin review has cleared
every flagged item. Nothing in this module ever invents question content,
option text, or an answer key.
"""
import logging

from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import (
    InvalidStateException,
    NotFoundException,
)
from app.common.services.base_service import BaseService
from app.common.utils.file_tracking import cleanup_drive_file, cleanup_drive_files
from app.core.enums import (
    DifficultyEnum,
    ExtractionConfidenceEnum,
    ImageSourceType,
    ProcessingStatusEnum,
    QuestionType,
    StatusEnum,
    WatermarkStatusEnum,
)
from app.core.google_drive import get_drive_client
from app.modules.paper.schema import PaperCreate
from app.modules.paper.service import paper_service
from app.modules.question.schema import OptionIn, QuestionCreate
from app.modules.question.service import question_service
from app.modules.subject.repository import SubjectRepository

from .model import ExtractedOption, ExtractedQuestion, ExtractedQuestionImage, PaperProcessingJob
from .pdf_generator import build_paper_pdf
from .repository import (
    ExtractedQuestionImageRepository,
    ExtractedQuestionRepository,
    PaperProcessingJobRepository,
)
from .schema import ExtractedQuestionIn, PaperProcessingJobCreate

logger = logging.getLogger(__name__)


# Defaults applied to every published question. Nothing in a source PDF
# reliably indicates question type, difficulty or mark weighting, so these
# are honest placeholders the admin edits afterwards through the normal
# Question edit UI - not inferences dressed up as data.
DEFAULT_QUESTION_TYPE = QuestionType.MCQ
DEFAULT_DIFFICULTY = DifficultyEnum.MEDIUM
DEFAULT_MARKS = 1.0
DEFAULT_NEGATIVE_MARKS = 0.0

# Question.correct_answer is NOT NULL in the existing schema. An extracted
# question whose answer the admin did not supply is published with this
# empty sentinel, which QuestionService.is_answer_correct can never match
# against a real submitted answer (a blank submission is rejected before it
# reaches scoring), so it can never mark a student spuriously correct.
NO_ANSWER_SENTINEL = ""

MIN_OPTIONS_TO_PUBLISH = 2

# Stages that mean "the pipeline stopped part-way" - either the process died
# before reaching a terminal state, or an admin asked it to stop. Shared
# with background.py (which imports this instead of the other way around,
# to avoid a circular import between the two modules).
IN_FLIGHT_STATUSES = (
    ProcessingStatusEnum.UPLOADED,
    ProcessingStatusEnum.VALIDATING,
    ProcessingStatusEnum.CLEANING_WATERMARK,
    ProcessingStatusEnum.ANALYZING,
    ProcessingStatusEnum.EXTRACTING,
    ProcessingStatusEnum.DETECTING_QUESTIONS,
)


class PaperProcessingService(BaseService):

    def __init__(self):
        super().__init__(PaperProcessingJobRepository())
        self._questions = ExtractedQuestionRepository()
        self._images = ExtractedQuestionImageRepository()
        self._subjects = SubjectRepository()

    # ------------------------------------------------------------ lookup --

    def get_job(self, db: Session, job_id: int) -> PaperProcessingJob:
        job = self.repository.get_with_questions(db, job_id)

        if job is None:
            raise NotFoundException("Processing job not found")

        return job

    def list_jobs(self, db: Session, limit: int = 100):
        return self.repository.list_recent(db, limit)

    def list_questions(self, db: Session, job_id: int):
        """Staged questions for one job, in admin-controlled order."""
        return self._questions.list_for_job(db, job_id)

    # ------------------------------------------------------------ create --

    def create_job(
        self,
        db: Session,
        admin_id: int,
        data: PaperProcessingJobCreate,
    ) -> PaperProcessingJob:

        subject = self._subjects.get_by_id(db, data.subject_id)

        if subject is None:
            raise NotFoundException(f"Subject {data.subject_id} does not exist")

        job = PaperProcessingJob(
            admin_id=admin_id,
            subject_id=data.subject_id,
            title=data.title,
            year=data.year,
            source_url=data.source_url,
            source_notes=data.source_notes,
            original_file_id=data.original_file_id,
            original_mime_type=data.original_mime_type,
            original_file_size=data.original_file_size,
            original_filename=data.original_filename,
            answer_file_id=data.answer_file_id,
            answer_mime_type=data.answer_mime_type,
            answer_file_size=data.answer_file_size,
            answer_filename=data.answer_filename,
            status=ProcessingStatusEnum.UPLOADED,
            watermark_status=WatermarkStatusEnum.NOT_NEEDED,
            ocr_used=False,
        )

        return self.repository.create(db, job)

    # ------------------------------------------------------- pipeline io --

    def set_status(
        self,
        db: Session,
        job: PaperProcessingJob,
        status: ProcessingStatusEnum,
        error_message: str | None = None,
    ) -> PaperProcessingJob:
        job.status = status
        job.error_message = error_message
        db.commit()
        db.refresh(job)
        return job

    def fail_job(
        self,
        db: Session,
        job: PaperProcessingJob,
        message: str,
        status: ProcessingStatusEnum = ProcessingStatusEnum.FAILED,
    ) -> PaperProcessingJob:
        """`message` must already be user-safe - tracebacks are logged only."""
        return self.set_status(db, job, status, message)

    def request_cancel(self, db: Session, job_id: int) -> PaperProcessingJob:
        """
        Asks a running job to stop at its next stage checkpoint. This is
        cooperative, not a hard kill - there is no task queue to interrupt a
        thread outright, so `background.run_pipeline` checks this flag
        between stages and stops there, marking the job FAILED with a clear
        "stopped by an admin" message rather than silently vanishing.
        """
        job = self.get_job(db, job_id)

        if job.status not in IN_FLIGHT_STATUSES:
            raise InvalidStateException("This job is not currently running.")

        job.cancel_requested = True
        db.commit()
        db.refresh(job)
        logger.info("Job %s: stop requested by admin (currently %s)", job.id, job.status.value)

        return job

    def is_cancel_requested(self, db: Session, job: PaperProcessingJob) -> bool:
        """Re-reads the flag fresh from the DB - `job` may be a long-lived
        in-memory object the background pipeline has held across several
        commits, and the cancel request comes from a separate request/session."""
        db.refresh(job, attribute_names=["cancel_requested"])
        return job.cancel_requested

    def replace_extracted_questions(
        self,
        db: Session,
        job: PaperProcessingJob,
        parsed_questions,
        ocr_used: bool,
        visuals: dict | None = None,
    ) -> None:
        """
        Writes a fresh parse into the staging tables, discarding any previous
        parse for this job. Only ever called by the pipeline, before review.

        `visuals` (optional) is {parsed_question_index: [VisualCandidate,
        ...]} from `question_visuals.detect_question_visuals` - each
        candidate's raw bytes are uploaded to Drive and attached as an
        ExtractedQuestionImage row on the matching question. A candidate
        that fails to upload is logged and skipped rather than losing the
        whole question - a missing diagram is a real, visible gap the admin
        will notice on the review screen, not a reason to fail the job.
        """
        job.extracted_questions.clear()
        db.flush()

        drive = get_drive_client() if visuals else None
        total_images = sum(len(v) for v in (visuals or {}).values())
        uploaded_so_far = 0

        if total_images:
            logger.info(
                "Job %s: uploading %d detected image(s) to Drive - this is one "
                "network call per image and is the slow part of this stage",
                job.id, total_images,
            )

        for index, parsed in enumerate(parsed_questions, start=1):
            question = ExtractedQuestion(
                order_index=index,
                question_number=parsed.question_number,
                question_text=parsed.question_text,
                raw_source_text=parsed.raw_source_text,
                confidence=parsed.confidence,
                needs_review=parsed.needs_review,
                # Never populated by extraction - admin input only.
                correct_answer=None,
                options=[
                    ExtractedOption(label=option.label, option_text=option.option_text)
                    for option in parsed.options
                ],
            )

            candidates = (visuals or {}).get(index - 1, [])
            if candidates:
                images = []
                any_region_render = False

                for order, candidate in enumerate(candidates, start=1):
                    try:
                        result = drive.upload_file(
                            candidate.image_bytes,
                            filename=f"q{parsed.question_number or index}-{order}.{candidate.ext}",
                            mime_type=f"image/{candidate.ext}" if candidate.ext != "jpg" else "image/jpeg",
                            category="question_images",
                        )
                    except Exception:
                        logger.exception(
                            "Could not upload a detected question image (job %s, question %s)",
                            job.id, index,
                        )
                        continue
                    finally:
                        uploaded_so_far += 1
                        # Every image, not batched - this is exactly the
                        # progress signal that was missing while this stage
                        # runs quietly for a long time on a big paper.
                        logger.info(
                            "Job %s: uploaded image %d/%d (question %s)",
                            job.id, uploaded_so_far, total_images, index,
                        )

                    images.append(ExtractedQuestionImage(
                        order_index=order,
                        file_id=result.file_id,
                        mime_type=result.mime_type,
                        file_size=result.file_size,
                        filename=result.name,
                        source_type=candidate.source_type,
                        page_number=candidate.page_number,
                        bbox_x0=candidate.bbox[0],
                        bbox_y0=candidate.bbox[1],
                        bbox_x1=candidate.bbox[2],
                        bbox_y1=candidate.bbox[3],
                    ))

                    if candidate.source_type == ImageSourceType.REGION_RENDER:
                        any_region_render = True

                question.images = images

                if any_region_render:
                    # The loosest signal - a geometric gap, not a confirmed
                    # image or drawing object - always gets a human look.
                    question.needs_review = True

            job.extracted_questions.append(question)

            if candidates:
                # Touches `updated_at` as real progress happens, not just at
                # the end - this is what lets the status page tell "still
                # actively uploading images" apart from "actually stuck"
                # (see background.is_stuck), on a stage that can otherwise
                # run for minutes with no visible commit at all.
                db.flush()
                db.commit()

        if total_images:
            logger.info("Job %s: finished uploading images", job.id)

        job.ocr_used = ocr_used
        db.flush()
        self.resync_counters(db, job)

    def resync_counters(self, db: Session, job: PaperProcessingJob) -> None:
        questions = self._questions.list_for_job(db, job.id)

        job.questions_extracted = len(questions)
        job.questions_low_confidence = sum(
            1 for question in questions
            if question.confidence == ExtractionConfidenceEnum.LOW
        )

        db.commit()
        db.refresh(job)

    # -------------------------------------------------------- review edit --

    def _editable_job(self, db: Session, job_id: int) -> PaperProcessingJob:
        job = self.get_job(db, job_id)

        if job.status == ProcessingStatusEnum.PUBLISHED:
            raise InvalidStateException(
                "This paper has already been published and can no longer be edited."
            )

        return job

    def _reopen_for_review(self, job: PaperProcessingJob) -> None:
        """
        Any content change after the admin pressed "Save review" invalidates
        the generated PDF, so the job drops back to READY_FOR_REVIEW and the
        PDF must be regenerated before publishing.
        """
        if job.status in (
            ProcessingStatusEnum.REVIEWED,
            ProcessingStatusEnum.READY_TO_PUBLISH,
        ):
            job.status = ProcessingStatusEnum.READY_FOR_REVIEW

    def get_question(
        self,
        db: Session,
        job_id: int,
        question_id: int,
    ) -> ExtractedQuestion:
        question = self._questions.get_for_job(db, job_id, question_id)

        if question is None:
            raise NotFoundException("Extracted question not found for this job")

        return question

    def update_question(
        self,
        db: Session,
        job_id: int,
        question_id: int,
        data: ExtractedQuestionIn,
    ) -> ExtractedQuestion:

        job = self._editable_job(db, job_id)
        question = self.get_question(db, job_id, question_id)

        question.question_text = data.question_text.strip()
        question.question_number = data.question_number

        # Blank means "Answer Key: Not Available" - stored as NULL, never as
        # a guess.
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
            question.options.append(ExtractedOption(
                label=option.label.strip().upper()[:2],
                option_text=text,
            ))

        self._reopen_for_review(job)
        db.commit()
        db.refresh(question)
        self.resync_counters(db, job)

        return question

    def set_needs_review(
        self,
        db: Session,
        job_id: int,
        question_id: int,
        needs_review: bool,
    ) -> ExtractedQuestion:
        self._editable_job(db, job_id)
        question = self.get_question(db, job_id, question_id)

        question.needs_review = needs_review
        db.commit()
        db.refresh(question)

        return question

    def add_question(
        self,
        db: Session,
        job_id: int,
        data: ExtractedQuestionIn,
    ) -> ExtractedQuestion:

        job = self._editable_job(db, job_id)

        answer = (data.correct_answer or "").strip()

        question = ExtractedQuestion(
            job_id=job.id,
            order_index=self._questions.max_order_index(db, job.id) + 1,
            question_number=data.question_number,
            question_text=data.question_text.strip(),
            # Hand-written by the admin, so there is no raw extraction to
            # compare against - left NULL rather than faking a source.
            raw_source_text=None,
            # An admin-authored question was reviewed by definition, at the
            # moment it was typed.
            confidence=ExtractionConfidenceEnum.HIGH,
            needs_review=bool(data.needs_review),
            correct_answer=answer or None,
            options=[
                ExtractedOption(
                    label=option.label.strip().upper()[:2],
                    option_text=option.option_text.strip(),
                )
                for option in data.options
                if option.option_text.strip()
            ],
        )

        db.add(question)
        self._reopen_for_review(job)
        db.commit()
        db.refresh(question)
        self.resync_counters(db, job)

        return question

    def delete_question(self, db: Session, job_id: int, question_id: int) -> None:
        job = self._editable_job(db, job_id)
        question = self.get_question(db, job_id, question_id)

        image_file_ids = [image.file_id for image in question.images]

        db.delete(question)
        db.flush()

        self._renumber(db, job)
        self._reopen_for_review(job)
        db.commit()
        self.resync_counters(db, job)

        # Only after the row is really gone, so a failed commit can never
        # leave a live row pointing at a deleted Drive file.
        cleanup_drive_files(db, image_file_ids)

    def move_question(
        self,
        db: Session,
        job_id: int,
        question_id: int,
        direction: str,
    ) -> None:
        """direction is "up" or "down"; out-of-range moves are a no-op."""
        job = self._editable_job(db, job_id)
        questions = self._questions.list_for_job(db, job_id)

        index = next(
            (i for i, question in enumerate(questions) if question.id == question_id),
            None,
        )

        if index is None:
            raise NotFoundException("Extracted question not found for this job")

        target = index - 1 if direction == "up" else index + 1

        if target < 0 or target >= len(questions):
            return

        questions[index], questions[target] = questions[target], questions[index]

        self._apply_order(db, questions)
        self._reopen_for_review(job)
        db.commit()

    def split_question(
        self,
        db: Session,
        job_id: int,
        question_id: int,
        split_at: int | None = None,
    ) -> list[ExtractedQuestion]:
        """
        Turns one block into two adjacent editable blocks.

        The server never guesses *where* a merged block should be cut. With
        no explicit offset it simply gives the admin the same real extracted
        text twice, both flagged for review, to trim by hand. Nothing is
        fabricated either way.
        """
        job = self._editable_job(db, job_id)
        question = self.get_question(db, job_id, question_id)

        source = question.raw_source_text or question.question_text

        if split_at is not None and 0 < split_at < len(source):
            first_text = source[:split_at].strip()
            second_text = source[split_at:].strip()
        else:
            first_text = source.strip()
            second_text = source.strip()

        questions = self._questions.list_for_job(db, job_id)
        index = next(i for i, item in enumerate(questions) if item.id == question_id)

        question.question_text = first_text
        question.confidence = ExtractionConfidenceEnum.LOW
        question.needs_review = True

        second = ExtractedQuestion(
            job_id=job.id,
            order_index=self._questions.max_order_index(db, job.id) + 1,
            question_number=None,
            question_text=second_text,
            raw_source_text=question.raw_source_text,
            confidence=ExtractionConfidenceEnum.LOW,
            needs_review=True,
            correct_answer=None,
        )

        db.add(second)
        db.flush()

        questions.insert(index + 1, second)
        self._apply_order(db, questions)

        self._reopen_for_review(job)
        db.commit()
        self.resync_counters(db, job)

        return [question, second]

    def merge_with_next(
        self,
        db: Session,
        job_id: int,
        question_id: int,
    ) -> ExtractedQuestion:
        """
        Concatenates this block's text with the next one's into a single
        editable block, flagged for review. Purely a starting point built
        from real extracted text - no auto-correction of the seam.
        """
        job = self._editable_job(db, job_id)
        questions = self._questions.list_for_job(db, job_id)

        index = next(
            (i for i, question in enumerate(questions) if question.id == question_id),
            None,
        )

        if index is None:
            raise NotFoundException("Extracted question not found for this job")

        if index + 1 >= len(questions):
            raise InvalidStateException("This is the last question - there is nothing to merge with.")

        first = questions[index]
        second = questions[index + 1]

        first.question_text = f"{first.question_text}\n{second.question_text}".strip()
        first.raw_source_text = "\n".join(
            part for part in (first.raw_source_text, second.raw_source_text) if part
        ) or None

        # The merged block keeps whichever options the two halves had, in
        # label order, re-labelled by position so A/B/C/D stay contiguous.
        merged_texts = [option.option_text for option in first.options]
        merged_texts += [option.option_text for option in second.options]

        first.options.clear()
        db.flush()

        for label, text in zip(("A", "B", "C", "D"), merged_texts):
            first.options.append(ExtractedOption(label=label, option_text=text))

        first.confidence = ExtractionConfidenceEnum.LOW
        first.needs_review = True

        # Images belong to the paper, not to where a boundary happened to
        # fall - merging two blocks must never silently drop a diagram, so
        # the second block's images move onto the merged question instead
        # of being deleted, appended after whatever the first already had.
        next_order = max((image.order_index for image in first.images), default=0) + 1
        for image in list(second.images):
            image.extracted_question = first
            image.order_index = next_order
            next_order += 1

        db.delete(second)
        db.flush()

        self._renumber(db, job)
        self._reopen_for_review(job)
        db.commit()
        db.refresh(first)
        self.resync_counters(db, job)

        return first

    def _renumber(self, db: Session, job: PaperProcessingJob) -> None:
        self._apply_order(db, self._questions.list_for_job(db, job.id))

    def _apply_order(self, db: Session, questions: list[ExtractedQuestion]) -> None:
        """
        Rewrites order_index 1..N in list order.

        Done in two passes through negative values: (job_id, order_index) is
        unique, so assigning final positions directly would transiently
        collide with a row that has not moved yet.
        """
        for offset, question in enumerate(questions, start=1):
            question.order_index = -offset
        db.flush()

        for offset, question in enumerate(questions, start=1):
            question.order_index = offset
        db.flush()

    # --------------------------------------------------------------- images --
    #
    # Diagrams/figures found automatically are attached by
    # `replace_extracted_questions` during the pipeline run. Everything here
    # is the admin's manual correction of that: attaching one the pipeline
    # missed, replacing/removing a wrong association, or moving one to the
    # question it actually belongs to. None of it ever alters the image
    # bytes themselves - only which question a Drive file_id belongs to.

    def _get_image(
        self, db: Session, job_id: int, question_id: int, image_id: int
    ) -> ExtractedQuestionImage:
        question = self.get_question(db, job_id, question_id)
        image = self._images.get_for_question(db, question.id, image_id)

        if image is None:
            raise NotFoundException("Image not found for this question")

        return image

    def add_manual_image(
        self,
        db: Session,
        job_id: int,
        question_id: int,
        file_id: str,
        mime_type: str | None,
        file_size: int | None,
        filename: str | None,
    ) -> ExtractedQuestionImage:
        job = self._editable_job(db, job_id)
        question = self.get_question(db, job_id, question_id)

        image = ExtractedQuestionImage(
            extracted_question_id=question.id,
            order_index=self._images.max_order_index(db, question.id) + 1,
            file_id=file_id,
            mime_type=mime_type,
            file_size=file_size,
            filename=filename,
            source_type=ImageSourceType.MANUAL,
        )

        db.add(image)
        self._reopen_for_review(job)
        db.commit()
        db.refresh(image)

        return image

    def replace_image(
        self,
        db: Session,
        job_id: int,
        question_id: int,
        image_id: int,
        file_id: str,
        mime_type: str | None,
        file_size: int | None,
        filename: str | None,
    ) -> ExtractedQuestionImage:
        """Admin picked a different file for an existing image slot - the
        original extraction may have been wrong. The old Drive file is only
        cleaned up after the new one is safely referenced."""
        job = self._editable_job(db, job_id)
        image = self._get_image(db, job_id, question_id, image_id)

        old_file_id = image.file_id
        image.file_id = file_id
        image.mime_type = mime_type
        image.file_size = file_size
        image.filename = filename
        image.source_type = ImageSourceType.MANUAL

        self._reopen_for_review(job)
        db.commit()
        db.refresh(image)

        if old_file_id and old_file_id != file_id:
            cleanup_drive_file(db, old_file_id)

        return image

    def remove_image(self, db: Session, job_id: int, question_id: int, image_id: int) -> None:
        job = self._editable_job(db, job_id)
        image = self._get_image(db, job_id, question_id, image_id)

        file_id = image.file_id
        db.delete(image)
        self._reopen_for_review(job)
        db.commit()

        cleanup_drive_file(db, file_id)

    def reassign_image(
        self,
        db: Session,
        job_id: int,
        question_id: int,
        image_id: int,
        target_question_id: int,
    ) -> ExtractedQuestionImage:
        """Moves one image to a different question in the same job - for
        when a diagram was associated with the wrong question."""
        job = self._editable_job(db, job_id)
        image = self._get_image(db, job_id, question_id, image_id)
        target = self.get_question(db, job_id, target_question_id)

        image.extracted_question_id = target.id
        image.order_index = self._images.max_order_index(db, target.id) + 1

        self._reopen_for_review(job)
        db.commit()
        db.refresh(image)

        return image

    def move_image(
        self,
        db: Session,
        job_id: int,
        question_id: int,
        image_id: int,
        direction: str,
    ) -> None:
        """direction is "up" or "down"; out-of-range moves are a no-op."""
        job = self._editable_job(db, job_id)
        question = self.get_question(db, job_id, question_id)
        images = sorted(question.images, key=lambda image: image.order_index)

        index = next((i for i, image in enumerate(images) if image.id == image_id), None)
        if index is None:
            raise NotFoundException("Image not found for this question")

        target = index - 1 if direction == "up" else index + 1
        if target < 0 or target >= len(images):
            return

        images[index], images[target] = images[target], images[index]
        for offset, image in enumerate(images, start=1):
            image.order_index = offset

        self._reopen_for_review(job)
        db.commit()

    # ------------------------------------------------------------ review --

    def mark_reviewed(self, db: Session, job_id: int) -> PaperProcessingJob:
        job = self._editable_job(db, job_id)

        if not job.extracted_questions:
            raise InvalidStateException(
                "There are no questions to save. Add at least one question first."
            )

        job.status = ProcessingStatusEnum.REVIEWED
        job.error_message = None
        db.commit()
        db.refresh(job)

        return job

    # -------------------------------------------------------- generation --

    def generate_pdf(self, db: Session, job_id: int) -> PaperProcessingJob:
        job = self.get_job(db, job_id)

        if job.status not in (
            ProcessingStatusEnum.REVIEWED,
            ProcessingStatusEnum.READY_TO_PUBLISH,
        ):
            raise InvalidStateException(
                "Finish and save the review before generating the paper PDF."
            )

        questions = self._questions.list_for_job(db, job.id)

        if not questions:
            raise InvalidStateException("There are no reviewed questions to put in the PDF.")

        subject = job.subject
        department = subject.department if subject else None
        exam = department.exam if department else None

        job.status = ProcessingStatusEnum.GENERATING_PDF
        db.commit()

        drive = get_drive_client()

        try:
            content = build_paper_pdf(
                title=job.title,
                year=job.year,
                subject_name=subject.name if subject else None,
                department_name=department.name if department else None,
                exam_name=exam.name if exam else None,
                questions=questions,
                image_loader=drive.download_file,
            )

            filename = f"{job.title} ({job.year}) - LearnIn.pdf"

            result = drive.upload_file(
                content,
                filename=filename,
                mime_type="application/pdf",
                category="papers",
            )
        except Exception:
            logger.exception("Failed to generate/upload the paper PDF for job %s", job.id)
            job.status = ProcessingStatusEnum.REVIEWED
            job.error_message = (
                "The standardized PDF could not be generated. Please try again, "
                "or contact an administrator if this keeps happening."
            )
            db.commit()
            raise InvalidStateException(job.error_message)

        # A regenerated PDF supersedes the previous one - delete it so
        # abandoned generations do not pile up in Drive.
        superseded = job.generated_file_id

        job.generated_file_id = result.file_id
        job.generated_mime_type = result.mime_type
        job.generated_file_size = result.file_size
        job.generated_filename = result.name
        job.status = ProcessingStatusEnum.READY_TO_PUBLISH
        job.error_message = None
        db.commit()
        db.refresh(job)

        if superseded and superseded != result.file_id:
            cleanup_drive_file(db, superseded)

        return job

    # ----------------------------------------------------------- publish --

    def publish_blockers(self, db: Session, job: PaperProcessingJob) -> list[str]:
        """
        Everything standing between this job and a published Paper, as
        admin-readable sentences. Empty list means publishing is allowed.
        """
        blockers: list[str] = []

        if not job.title or not job.title.strip():
            blockers.append("A paper title is required.")

        if not job.year:
            blockers.append("A paper year is required.")

        if not job.subject_id:
            blockers.append("A subject is required.")

        questions = self._questions.list_for_job(db, job.id)

        if not questions:
            blockers.append("At least one question is required.")

        for question in questions:
            if not question.question_text or not question.question_text.strip():
                blockers.append(
                    f"Question {question.order_index} has no text."
                )
            if len(question.options) < MIN_OPTIONS_TO_PUBLISH:
                blockers.append(
                    f"Question {question.order_index} has fewer than "
                    f"{MIN_OPTIONS_TO_PUBLISH} options."
                )

        flagged = [q.order_index for q in questions if q.needs_review]
        if flagged:
            # Concrete gate: every item the pipeline (or the admin) flagged
            # must be explicitly cleared. "Reviewed" has to mean somebody
            # actually looked at the doubtful ones.
            blockers.append(
                "These questions are still marked for review: "
                + ", ".join(str(index) for index in flagged)
                + ". Clear each one before publishing."
            )

        if not job.generated_file_id:
            blockers.append("Generate the standardized PDF before publishing.")

        return blockers

    def questions_with_extra_images(self, db: Session, job: PaperProcessingJob) -> int:
        """Count of staged questions carrying more than one associated image -
        an informational note for the preview screen, never a publish
        blocker, since Question.image_file_id is a single slot (see
        `publish_job`)."""
        return sum(1 for q in self._questions.list_for_job(db, job.id) if len(q.images) > 1)

    def publish_job(self, db: Session, job_id: int):
        job = self.get_job(db, job_id)

        if job.status == ProcessingStatusEnum.PUBLISHED:
            raise InvalidStateException("This paper has already been published.")

        blockers = self.publish_blockers(db, job)

        if blockers:
            raise InvalidStateException(" ".join(blockers))

        paper = paper_service.create_paper(db, PaperCreate(
            subject_id=job.subject_id,
            title=job.title,
            year=job.year,
            question_file_id=job.generated_file_id,
            question_file_mime_type=job.generated_mime_type,
            question_file_size=job.generated_file_size,
            question_filename=job.generated_filename,
            answer_file_id=job.answer_file_id,
            answer_file_mime_type=job.answer_mime_type,
            answer_file_size=job.answer_file_size,
            answer_filename=job.answer_filename,
            status=StatusEnum.DRAFT,
        ))

        for question in self._questions.list_for_job(db, job.id):
            # Question.image_file_id (the existing, real schema) is a single
            # slot - it did not change for this feature, since that would
            # ripple into mock tests/practice pages far beyond this pipeline.
            # A question with more than one associated image publishes with
            # its first (lowest order_index) as the primary image; any
            # additional ones stay visible on the processing job's review
            # screen (never silently deleted) but do not currently reach the
            # published Question - see `publish_job`'s docstring note.
            primary_image = question.images[0] if question.images else None

            question_service.create_question(db, QuestionCreate(
                paper_id=paper.id,
                question_number=question.order_index,
                question_type=DEFAULT_QUESTION_TYPE,
                difficulty=DEFAULT_DIFFICULTY,
                question_text=question.question_text,
                image_file_id=primary_image.file_id if primary_image else None,
                image_mime_type=primary_image.mime_type if primary_image else None,
                image_file_size=primary_image.file_size if primary_image else None,
                image_filename=primary_image.filename if primary_image else None,
                marks=DEFAULT_MARKS,
                negative_marks=DEFAULT_NEGATIVE_MARKS,
                correct_answer=(question.correct_answer or NO_ANSWER_SENTINEL),
                options=[
                    OptionIn(label=option.label, option_text=option.option_text)
                    for option in question.options
                ],
                status=StatusEnum.DRAFT,
            ))

        job.paper_id = paper.id
        job.status = ProcessingStatusEnum.PUBLISHED
        job.error_message = None
        db.commit()
        db.refresh(job)

        return paper


paper_processing_service = PaperProcessingService()
