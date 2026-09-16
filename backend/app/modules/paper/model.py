from typing import TYPE_CHECKING

from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.core.base import BaseModel
from app.core.enums import PaperTypeEnum
from app.core.mixins import StatusMixin

if TYPE_CHECKING:
    from app.modules.mock_test.model import MockTest
    from app.modules.question.model import Question
    from app.modules.subject.model import Subject


class Paper(
    BaseModel,
    StatusMixin
):

    __tablename__ = "papers"

    __table_args__ = (
        UniqueConstraint("subject_id", "year", name="uq_subject_year"),
    )

    subject_id: Mapped[int] = mapped_column(
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

    question_file_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    question_file_mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    question_file_size: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    question_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    answer_file_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    answer_file_mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    answer_file_size: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    answer_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    duration: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    total_questions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    # Nullable: set by the admin at upload time (see paper_processing), left
    # unset for papers created before this existed - never guessed after
    # the fact from the paper's content.
    paper_type: Mapped["PaperTypeEnum | None"] = mapped_column(
        Enum(PaperTypeEnum, name="papertypeenum"),
        nullable=True
    )

    # "Use This Paper For" (see PaperUsageEnum / paper_processing/service.py
    # apply_usage) - lives here, not only on the PaperProcessingJob that
    # may have created this Paper, so usage can be set/changed for ANY
    # paper: one published through the pipeline, one created directly
    # through the generic admin CRUD, or one that predates this feature
    # entirely (NULL/empty here until an admin sets it). A comma-separated
    # list for the same portability reason as PaperProcessingJob.usage_flags
    # - never read/written except through the list/set helpers below.
    usage_flags: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def usage_flags_list(self) -> list[str]:
        return [flag for flag in (self.usage_flags or "").split(",") if flag]

    def set_usage_flags(self, flags: list[str]) -> None:
        self.usage_flags = ",".join(dict.fromkeys(flags)) or None

    subject: Mapped["Subject"] = relationship(
        back_populates="papers"
    )

    questions: Mapped[list["Question"]] = relationship(
        back_populates="paper",
        cascade="all, delete-orphan"
    )

    mock_tests: Mapped[list["MockTest"]] = relationship(
        back_populates="paper",
        cascade="all, delete-orphan"
    )
