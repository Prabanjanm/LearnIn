"""
Institution-owned equivalent of the paper_processing module.

An institution uploads its own PDF, runs it through the same kind of
validate -> watermark-clean -> OCR/extract -> parse pipeline as the
platform admin's Paper Processing workflow, reviews/corrects the result,
then confirms it. The published result never touches the public
`papers`/`questions` tables - it lands in ConductedTestPaper/
ConductedTestQuestion/ConductedTestOption instead, each row tagged with
institution_id, so institution-uploaded content can never leak into the
public catalog and one institution can never see another's papers.

Deliberately narrower than paper_processing: no subject/year/answer-key
metadata (an institution's own paper isn't part of the public exam
catalog), no re-branded PDF regeneration (the cleaned/original upload is
used as-is), and no diagram/image extraction (MCQ text+options only, a
scoped-down v1). These match the same trims already applied elsewhere in
this workflow - not accidental omissions.

Every table's `id` (and every foreign key here) is a UUID, via
BaseModel's own `id` column and `Uuid(as_uuid=True)` on every FK -
matching the rest of the codebase's primary key convention.
"""
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import BaseModel
from app.core.enums import (
    DifficultyEnum,
    ExtractionConfidenceEnum,
    PdfTypeEnum,
    ProcessingStatusEnum,
    QuestionType,
    WatermarkStatusEnum,
)

if TYPE_CHECKING:
    from app.modules.institution.model import Institution, InstitutionUser


class ConductedTestPaperJob(BaseModel):
    """One institution user's attempt to turn one uploaded PDF into a
    ConductedTestPaper. Mirrors PaperProcessingJob's shape/lifecycle
    (see that module's docstring) minus admin/subject/year/answer-key,
    which don't apply to an institution's own paper."""

    __tablename__ = "conducted_test_paper_jobs"

    institution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("institutions.id"), nullable=False, index=True
    )

    created_by_institution_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("institution_users.id"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)

    original_file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    original_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    original_file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Populated only when watermark cleaning actually removed something -
    # see PaperProcessingJob.cleaned_file_id for the same convention.
    cleaned_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cleaned_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cleaned_file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cleaned_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[ProcessingStatusEnum] = mapped_column(
        Enum(ProcessingStatusEnum, name="processingstatusenum"),
        default=ProcessingStatusEnum.UPLOADED,
        nullable=False,
        index=True,
    )

    pdf_type: Mapped[PdfTypeEnum | None] = mapped_column(
        Enum(PdfTypeEnum, name="pdftypeenum"), nullable=True
    )

    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    watermark_status: Mapped[WatermarkStatusEnum] = mapped_column(
        Enum(WatermarkStatusEnum, name="watermarkstatusenum"),
        default=WatermarkStatusEnum.NOT_NEEDED,
        nullable=False,
    )

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Cooperative cancellation - same convention as PaperProcessingJob.
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    conducted_test_paper_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("conducted_test_papers.id"), nullable=True, index=True
    )

    questions_extracted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    questions_low_confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    institution: Mapped["Institution"] = relationship("Institution")
    created_by_user: Mapped["InstitutionUser"] = relationship("InstitutionUser")

    extracted_questions: Mapped[list["ConductedTestExtractedQuestion"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="ConductedTestExtractedQuestion.order_index",
    )

    @property
    def effective_source_file_id(self) -> str:
        return self.cleaned_file_id or self.original_file_id


class ConductedTestExtractedQuestion(BaseModel):
    """Staging row - never shown to a student. Mirrors
    paper_processing.ExtractedQuestion exactly (minus images - see this
    module's docstring)."""

    __tablename__ = "conducted_test_extracted_questions"

    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("conducted_test_paper_jobs.id"), nullable=False, index=True
    )

    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    question_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    question_text: Mapped[str] = mapped_column(Text, nullable=False)

    raw_source_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    confidence: Mapped[ExtractionConfidenceEnum] = mapped_column(
        Enum(ExtractionConfidenceEnum, name="extractionconfidenceenum"), nullable=False
    )

    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ONLY ever set by explicit institution-user input on the review
    # screen - the pipeline never infers an answer.
    correct_answer: Mapped[str | None] = mapped_column(String(50), nullable=True)

    job: Mapped["ConductedTestPaperJob"] = relationship(back_populates="extracted_questions")

    options: Mapped[list["ConductedTestExtractedOption"]] = relationship(
        back_populates="extracted_question",
        cascade="all, delete-orphan",
        order_by="ConductedTestExtractedOption.label",
    )

    __table_args__ = (
        UniqueConstraint("job_id", "order_index", name="uq_ct_extracted_question_order"),
    )


class ConductedTestExtractedOption(BaseModel):

    __tablename__ = "conducted_test_extracted_options"

    extracted_question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("conducted_test_extracted_questions.id"), nullable=False, index=True
    )

    label: Mapped[str] = mapped_column(String(2), nullable=False)

    option_text: Mapped[str] = mapped_column(Text, nullable=False)

    extracted_question: Mapped["ConductedTestExtractedQuestion"] = relationship(back_populates="options")

    __table_args__ = (
        UniqueConstraint("extracted_question_id", "label", name="uq_ct_extracted_option_label"),
    )


class ConductedTestPaper(BaseModel):
    """The confirmed, institution-owned result of one job - the
    institution-scoped equivalent of a public Paper. Never listed
    publicly; only ever selectable by the same institution when creating
    a ConductedTest (see conducted_test/model.py)."""

    __tablename__ = "conducted_test_papers"

    institution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("institutions.id"), nullable=False, index=True
    )

    created_by_institution_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("institution_users.id"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)

    question_file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    question_file_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    question_file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    question_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    total_questions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    institution: Mapped["Institution"] = relationship("Institution")
    created_by_user: Mapped["InstitutionUser"] = relationship("InstitutionUser")

    questions: Mapped[list["ConductedTestQuestion"]] = relationship(
        back_populates="conducted_test_paper",
        cascade="all, delete-orphan",
        order_by="ConductedTestQuestion.question_number",
    )


class ConductedTestQuestion(BaseModel):
    """Institution-scoped equivalent of Question - deliberately the same
    shape (question_type/correct_answer/marks/negative_marks/difficulty)
    so it can be graded by the exact same evaluate_answer logic
    (app.modules.question.service.question_service.evaluate_answer),
    which only ever reads those attributes and doesn't care which table
    they came from."""

    __tablename__ = "conducted_test_questions"

    conducted_test_paper_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("conducted_test_papers.id"), nullable=False, index=True
    )

    question_number: Mapped[int] = mapped_column(Integer, nullable=False)

    question_type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, name="questiontype"), nullable=False
    )

    question_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Empty string ("") is the same "no answer key available" sentinel
    # question_service uses - see paper_processing's publish_job.
    correct_answer: Mapped[str] = mapped_column(String(50), nullable=False)

    marks: Mapped[float] = mapped_column(nullable=False)
    negative_marks: Mapped[float] = mapped_column(nullable=False)

    difficulty: Mapped[DifficultyEnum | None] = mapped_column(
        Enum(DifficultyEnum, name="difficultyenum"), nullable=True
    )

    conducted_test_paper: Mapped["ConductedTestPaper"] = relationship(back_populates="questions")

    options: Mapped[list["ConductedTestOption"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="ConductedTestOption.label",
    )

    __table_args__ = (
        UniqueConstraint("conducted_test_paper_id", "question_number", name="uq_ct_question_number"),
    )


class ConductedTestOption(BaseModel):

    __tablename__ = "conducted_test_options"

    conducted_test_question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("conducted_test_questions.id"), nullable=False, index=True
    )

    label: Mapped[str] = mapped_column(String(2), nullable=False)

    option_text: Mapped[str] = mapped_column(Text, nullable=False)

    question: Mapped["ConductedTestQuestion"] = relationship(back_populates="options")

    __table_args__ = (
        UniqueConstraint("conducted_test_question_id", "label", name="uq_ct_option_label"),
    )
