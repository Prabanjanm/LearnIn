"""
Staging tables for the "Question Paper Processing" admin workflow.

`ExtractedQuestion` / `ExtractedOption` are deliberately NOT the real
`questions` / `options` tables. Nothing machine-extracted is ever exposed to
a student: the pipeline writes here, an admin reviews and corrects every
row by hand, and only the explicit publish step creates real
`Question`/`Option` rows. That separation is the whole point of these
tables - do not shortcut it.
"""
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy import Uuid

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from sqlalchemy import Float

from app.core.base import BaseModel
from app.core.enums import ExtractionConfidenceEnum
from app.core.enums import ImageSourceType
from app.core.enums import PaperTypeEnum
from app.core.enums import PdfTypeEnum
from app.core.enums import ProcessingStatusEnum
from app.core.enums import QuestionType
from app.core.enums import WatermarkStatusEnum

if TYPE_CHECKING:
    from app.modules.admin.model import Admin
    from app.modules.paper.model import Paper
    from app.modules.subject.model import Subject


class PaperProcessingJob(BaseModel):
    """
    One admin's attempt to turn one collected source PDF into a published
    Paper. Exam/department are reachable through
    subject -> department -> exam, so they are not duplicated here.
    """

    __tablename__ = "paper_processing_jobs"

    admin_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admins.id"),
        nullable=False,
        index=True
    )

    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subjects.id"),
        nullable=False,
        index=True
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    year: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    # Set by the admin on the "new job" form, carried through unchanged to
    # the published Paper.paper_type at publish time.
    paper_type: Mapped["PaperTypeEnum | None"] = mapped_column(
        Enum(PaperTypeEnum, name="papertypeenum"),
        nullable=True
    )

    source_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True
    )

    source_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # The untouched upload. Never overwritten - watermark cleaning and PDF
    # generation always write to their own columns, so the admin can always
    # go back to exactly what was collected.
    original_file_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    original_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    original_file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Populated only when watermark cleaning actually removed something.
    # Left NULL when watermark_status is NOT_NEEDED or NEEDS_MANUAL_REVIEW -
    # readers should fall back to the original in that case (see
    # `effective_source_file_id`), which keeps "was anything cleaned?"
    # answerable from the data rather than by comparing file ids.
    cleaned_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    cleaned_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    cleaned_file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    cleaned_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # The standardized LearnIn-branded PDF built from the reviewed content.
    generated_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    generated_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    generated_file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    generated_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Optional admin-supplied answer key, carried through to the published
    # Paper completely unparsed. Nothing here is ever auto-graded.
    answer_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    answer_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    answer_file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    answer_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[ProcessingStatusEnum] = mapped_column(
        Enum(
            ProcessingStatusEnum,
            name="processingstatusenum"
        ),
        default=ProcessingStatusEnum.UPLOADED,
        nullable=False,
        index=True
    )

    pdf_type: Mapped[PdfTypeEnum | None] = mapped_column(
        Enum(
            PdfTypeEnum,
            name="pdftypeenum"
        ),
        nullable=True
    )

    ocr_used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    watermark_status: Mapped[WatermarkStatusEnum] = mapped_column(
        Enum(
            WatermarkStatusEnum,
            name="watermarkstatusenum"
        ),
        default=WatermarkStatusEnum.NOT_NEEDED,
        nullable=False
    )

    # Last user-safe error only. Tracebacks are logged, never stored here.
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Cooperative cancellation - there is no task queue to kill a running
    # job outright, so the background pipeline checks this flag between
    # stages (see background.py) and stops at the next checkpoint rather
    # than mid-stage. Reset to False whenever a fresh run starts.
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    paper_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("papers.id"),
        nullable=True,
        index=True
    )

    # What the admin picked in the "Use This Paper For" section - a
    # comma-separated list of PaperUsageEnum values (a real ARRAY type would
    # need a Postgres-only column; this stays portable and is only ever
    # read/written through usage_flags_list/set_usage_flags below, never by
    # hand). Applied to real rows (Resource/MockTest) by
    # PaperProcessingService.apply_usage, once at publish and again any
    # time the admin changes the selection afterward.
    usage_flags: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def usage_flags_list(self) -> list[str]:
        return [flag for flag in (self.usage_flags or "").split(",") if flag]

    def set_usage_flags(self, flags: list[str]) -> None:
        self.usage_flags = ",".join(dict.fromkeys(flags)) or None

    # Denormalized counters, resynced whenever extracted questions change,
    # mirroring how Paper.total_questions is kept in step.
    questions_extracted: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    questions_low_confidence: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    # Where this paper is headed once published: a Mock Test. Left NULL
    # (mock_test_title) when the admin only wants the Paper/Questions
    # published without a mock test - publish_job only creates a MockTest
    # when a title was supplied here.
    mock_test_title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    mock_test_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    mock_test_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)

    mock_test_total_marks: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships

    admin: Mapped["Admin"] = relationship("Admin")

    subject: Mapped["Subject"] = relationship("Subject")

    paper: Mapped["Paper | None"] = relationship("Paper")

    extracted_questions: Mapped[list["ExtractedQuestion"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="ExtractedQuestion.order_index"
    )

    @property
    def effective_source_file_id(self) -> str:
        """
        The PDF the pipeline should read from: the cleaned copy when one was
        produced, otherwise the untouched original.
        """
        return self.cleaned_file_id or self.original_file_id


class ExtractedQuestion(BaseModel):

    __tablename__ = "extracted_questions"

    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("paper_processing_jobs.id"),
        nullable=False,
        index=True
    )

    # Admin-controlled ordering. Reordering just rewrites these.
    order_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    # As detected in the source. Source numbering is often inconsistent
    # (restarts per section, skips numbers), so this is neither assumed
    # unique nor assumed sequential - order_index is the authority.
    question_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    question_text: Mapped[str] = mapped_column(Text, nullable=False)

    # The unedited block this question was segmented from, kept so the admin
    # can diff their correction against what was really extracted. Never
    # shown as if it were final content.
    raw_source_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    confidence: Mapped[ExtractionConfidenceEnum] = mapped_column(
        Enum(
            ExtractionConfidenceEnum,
            name="extractionconfidenceenum"
        ),
        nullable=False
    )

    # Manual flag layered on top of confidence: LOW auto-sets it at creation
    # time, but the admin can raise or clear it on any item.
    needs_review: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    # Admin input in the review screen, same as always - OR filled in
    # automatically when the admin also uploaded a separate "Answer Key" PDF
    # that could be parsed and matched to this question by number (see
    # `answer_key_parser.py` / `PaperProcessingService.apply_answer_key`).
    # Either way it is NULL until something concrete sets it - the pipeline
    # never fabricates an answer from the question paper's own text.
    correct_answer: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # The following three are NULL unless a matched answer-key row supplied
    # them (see `apply_answer_key`); `publish_job` falls back to its own
    # DEFAULT_* constants when NULL, exactly as it always has. Never set by
    # question-paper text extraction itself - only a literal answer-key
    # table is a reliable enough source for these.
    question_type: Mapped[QuestionType | None] = mapped_column(
        Enum(QuestionType, name="questiontype"),
        nullable=True
    )

    marks: Mapped[float | None] = mapped_column(Float, nullable=True)

    negative_marks: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships

    job: Mapped["PaperProcessingJob"] = relationship(
        back_populates="extracted_questions"
    )

    options: Mapped[list["ExtractedOption"]] = relationship(
        back_populates="extracted_question",
        cascade="all, delete-orphan",
        order_by="ExtractedOption.label"
    )

    # A question paper question is not always pure text - diagrams, graphs,
    # tables and figures are frequently the whole point of a question. A
    # question can carry any number of these (an ordered list, not a single
    # slot), each traceable back to where on the source PDF it came from.
    images: Mapped[list["ExtractedQuestionImage"]] = relationship(
        back_populates="extracted_question",
        cascade="all, delete-orphan",
        order_by="ExtractedQuestionImage.order_index"
    )

    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "order_index",
            name="uq_extracted_question_order"
        ),
    )


class ExtractedOption(BaseModel):

    __tablename__ = "extracted_options"

    extracted_question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_questions.id"),
        nullable=False,
        index=True
    )

    # Always normalized to A/B/C/D by the parser, whatever the source used
    # ("(a)", "1)", "A.", ...). The raw label style is not preserved -
    # raw_source_text on the parent keeps the original text if needed.
    label: Mapped[str] = mapped_column(
        String(2),
        nullable=False
    )

    option_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships

    extracted_question: Mapped["ExtractedQuestion"] = relationship(
        back_populates="options"
    )

    __table_args__ = (
        UniqueConstraint(
            "extracted_question_id",
            "label",
            name="uq_extracted_option_label"
        ),
    )


class ExtractedQuestionImage(BaseModel):
    """
    One visual asset (diagram, graph, table, scanned figure, ...) associated
    with a staged question.

    The pipeline never tries to describe, redraw or "understand" a diagram -
    it only ever preserves the original pixels, found one of three ways
    (`source_type`): a real embedded raster image, a vector drawing rendered
    to a raster crop because there is no faithful way to "extract" a vector
    path outside a PDF viewer, or a high-resolution render of a region whose
    text alone does not account for its size on the page. `page_number` and
    the `bbox_*` columns are exactly the PDF-coordinate evidence that placed
    it with this question, so an admin reviewing "does this image really
    belong to Q37?" is looking at the same geometry the pipeline used.
    """

    __tablename__ = "extracted_question_images"

    extracted_question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_questions.id"),
        nullable=False,
        index=True
    )

    # Admin-controlled ordering when a question has more than one image.
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    file_id: Mapped[str] = mapped_column(String(255), nullable=False)

    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    source_type: Mapped[ImageSourceType] = mapped_column(
        Enum(ImageSourceType, name="imagesourcetype"),
        nullable=False
    )

    # The page (0-indexed, matching PyMuPDF) and PDF-coordinate bounding box
    # this asset was found/rendered at, kept purely as review evidence - not
    # used for anything once the image is stored. NULL for a MANUAL upload,
    # which has no source position.
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    bbox_x0: Mapped[float | None] = mapped_column(Float, nullable=True)

    bbox_y0: Mapped[float | None] = mapped_column(Float, nullable=True)

    bbox_x1: Mapped[float | None] = mapped_column(Float, nullable=True)

    bbox_y1: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships

    extracted_question: Mapped["ExtractedQuestion"] = relationship(
        back_populates="images"
    )

    @property
    def thumbnail_url(self) -> str | None:
        """Used directly by the review screen's Jinja template (which
        renders these ORM rows straight, unlike the JSON API which goes
        through ExtractedQuestionImageResponse's identical computed field)."""
        from app.common.utils.drive_urls import drive_thumbnail_url
        return drive_thumbnail_url(self.file_id)

    @property
    def view_url(self) -> str | None:
        from app.common.utils.drive_urls import drive_view_url
        return drive_view_url(self.file_id)
