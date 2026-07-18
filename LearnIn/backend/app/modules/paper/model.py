from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.core.base import BaseModel
from app.core.mixins import StatusMixin

if TYPE_CHECKING:
    from app.modules.subject.model import Subject
    from app.modules.question.model import Question
    from app.modules.mock_test.model import MockTest


class Paper(
    BaseModel,
    StatusMixin
):
    __tablename__ = "papers"

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

    answer_file_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    duration: Mapped[int | None] = mapped_column(
        nullable=True
    )

    total_questions: Mapped[int] = mapped_column(
        default=0
    )

    # Relationships

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

    __table_args__ = (
        UniqueConstraint(
            "subject_id",
            "year",
            name="uq_subject_year"
        ),
    )