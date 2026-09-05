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
    from app.modules.department.model import Department
    from app.modules.paper.model import Paper
    from app.modules.resource.model import Resource


class Subject(
    BaseModel,
    SlugMixin,
    StatusMixin,
    SeoMixin
):

    __tablename__ = "subjects"

    __table_args__ = (
        UniqueConstraint("department_id", "slug", name="uq_department_subject"),
    )

    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id"),
        nullable=False,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(100),
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
