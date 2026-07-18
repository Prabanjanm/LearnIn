from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import relationship
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.core.base import BaseModel


class Option(BaseModel):

    __tablename__ = "options"

    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id"),
        nullable=False,
        index=True
    )

    label: Mapped[str] = mapped_column(
        String(2),
        nullable=False
    )

    option_text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    question = relationship(
    "Question",
    back_populates="options"
)
    
    __table_args__ = (
    UniqueConstraint(
        "question_id",
        "label",
        name="uq_option_label"
    ),
)