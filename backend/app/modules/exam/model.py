from typing import TYPE_CHECKING

from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
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


class Exam(
    BaseModel,
    SlugMixin,
    StatusMixin,
    SeoMixin
):

    __tablename__ = "exams"

    __table_args__ = (
        UniqueConstraint("code", name="uq_exams_code"),
        UniqueConstraint("name", name="uq_exams_name"),
        UniqueConstraint("slug", name="uq_exams_slug"),
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
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

    departments: Mapped[list["Department"]] = relationship(
        back_populates="exam",
        cascade="all, delete-orphan"
    )
