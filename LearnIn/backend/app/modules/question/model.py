from typing import TYPE_CHECKING

from sqlalchemy import Enum
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.core.base import BaseModel
from app.core.enums import DifficultyEnum
from app.core.enums import QuestionType
from app.core.mixins import StatusMixin

if TYPE_CHECKING:
    from app.modules.paper.model import Paper
    from app.modules.option.model import Option
    from app.modules.mock_test_question.model import MockTestQuestion


class Question(
    BaseModel,
    StatusMixin
):
    __tablename__ = "questions"

    paper_id: Mapped[int] = mapped_column(
        ForeignKey("papers.id"),
        nullable=False,
        index=True
    )

    question_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    question_type: Mapped[QuestionType] = mapped_column(
        Enum(
            QuestionType,
            name="questiontype"
        ),
        nullable=False
    )

    question_text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    image_file_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    correct_answer: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    explanation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    marks: Mapped[float] = mapped_column(
        Float,
        default=1
    )

    negative_marks: Mapped[float] = mapped_column(
        Float,
        default=0
    )

    difficulty: Mapped[DifficultyEnum] = mapped_column(
        Enum(
            DifficultyEnum,
            name="difficultyenum"
        ),
        nullable=False
    )

    # Relationships

    paper: Mapped["Paper"] = relationship(
        back_populates="questions"
    )

    options: Mapped[list["Option"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan"
    )

    mock_test_questions: Mapped[list["MockTestQuestion"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "paper_id",
            "question_number",
            name="uq_question_number"
        ),
    )