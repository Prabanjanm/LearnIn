from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import BaseModel
from app.core.mixins import SlugMixin, StatusMixin, SeoMixin

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

    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id"),
        nullable=False,
        index=True
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    code: Mapped[str] = mapped_column(String(20), nullable=False)

    display_order: Mapped[int] = mapped_column(default=0)

    icon_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    icon_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    icon_file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    icon_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    exam: Mapped["Exam"] = relationship(
        back_populates="departments"
    )

    subjects: Mapped[list["Subject"]] = relationship(
        back_populates="department",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "exam_id",
            "code",
            name="uq_exam_department"
        ),
        UniqueConstraint(
            "exam_id",
            "slug",
            name="uq_exam_department_slug"
        ),
    )