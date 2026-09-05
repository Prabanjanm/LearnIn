from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.core.base import BaseModel
from app.core.mixins import StatusMixin

if TYPE_CHECKING:
    from app.modules.mock_test_question.model import MockTestQuestion
    from app.modules.paper.model import Paper


class MockTest(
    BaseModel,
    StatusMixin
):

    __tablename__ = "mock_tests"

    paper_id: Mapped[int] = mapped_column(
        ForeignKey("papers.id"),
        nullable=False,
        index=True
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    duration: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    total_marks: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    total_questions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    # Relationships
    paper: Mapped["Paper"] = relationship(
        back_populates="mock_tests"
    )

    questions: Mapped[list["MockTestQuestion"]] = relationship(
        back_populates="mock_test",
        cascade="all, delete-orphan",
        order_by="MockTestQuestion.question_order"
    )
