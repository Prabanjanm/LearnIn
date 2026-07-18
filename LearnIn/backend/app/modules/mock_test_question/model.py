from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy import Integer

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.core.base import BaseModel

if TYPE_CHECKING:
    from app.modules.mock_test.model import MockTest
    from app.modules.question.model import Question


class MockTestQuestion(BaseModel):

    __tablename__ = "mock_test_questions"

    mock_test_id: Mapped[int] = mapped_column(
        ForeignKey("mock_tests.id"),
        nullable=False,
        index=True
    )

    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id"),
        nullable=False,
        index=True
    )

    question_order: Mapped[int] = mapped_column(
        Integer,
        default=1
    )

    # Relationships
    mock_test: Mapped["MockTest"] = relationship(
        back_populates="questions"
    )

    question: Mapped["Question"] = relationship(
        back_populates="mock_test_questions"
    )