from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import BaseModel
from app.core.mixins import SlugMixin, StatusMixin, SeoMixin

if TYPE_CHECKING:
    from app.modules.department.model import Department
    from app.modules.paper.model import Paper
    from app.modules.resource.model import Resource
    from app.modules.mock_test.model import MockTest


class Subject(
    BaseModel,
    SlugMixin,
    StatusMixin,
    SeoMixin
):
    __tablename__ = "subjects"

    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id"),
        nullable=False,
        index=True
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    display_order: Mapped[int] = mapped_column(default=0)

    icon_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    icon_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    icon_file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    icon_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    department: Mapped["Department"] = relationship(
        back_populates="subjects"
    )

    papers: Mapped[list["Paper"]] = relationship(
        back_populates="subject",
        cascade="all, delete-orphan"
    )

    resources: Mapped[list["Resource"]] = relationship(
        back_populates="subject",
        cascade="all, delete-orphan"
    )

    # mock_tests: Mapped[list["MockTest"]] = relationship(
    #     back_populates="subject",
    #     cascade="all, delete-orphan"
    # )

    __table_args__ = (
        UniqueConstraint(
            "department_id",
            "slug",
            name="uq_department_subject"
        ),
    )