from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.core.base import BaseModel
from app.core.mixins import SeoMixin
from app.core.mixins import SlugMixin
from app.core.mixins import StatusMixin

if TYPE_CHECKING:
    from app.modules.exam.model import Exam
    from app.modules.subject.model import Subject


class Department(
    BaseModel,
    SlugMixin,
    StatusMixin,
    SeoMixin
):

    __tablename__ = "departments"

    __table_args__ = (
        UniqueConstraint("exam_id", "code", name="uq_exam_department"),
        UniqueConstraint("exam_id", "slug", name="uq_exam_department_slug"),
    )

    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id"),
        nullable=False,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    icon_file_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    icon_mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    icon_file_size: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    icon_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    exam: Mapped["Exam"] = relationship(
        back_populates="departments"
    )

    subjects: Mapped[list["Subject"]] = relationship(
        back_populates="department",
        cascade="all, delete-orphan"
    )
