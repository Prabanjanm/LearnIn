from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import BaseModel
from app.core.mixins import SlugMixin, StatusMixin, SeoMixin

if TYPE_CHECKING:
    from app.modules.department.model import Department


class Exam(
    BaseModel,
    SlugMixin,
    StatusMixin,
    SeoMixin
):
    __tablename__ = "exams"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Uploaded via the admin's automatic Drive upload widget - the actual
    # image lives in Drive, only its metadata is stored here. URLs are
    # never persisted; they're derived from icon_file_id on demand
    # (see app.common.utils.drive_urls).
    icon_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    icon_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    icon_file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    icon_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    display_order: Mapped[int] = mapped_column(default=0)

    # ✅ INSIDE the class
    departments: Mapped[list["Department"]] = relationship(
        back_populates="exam",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("slug", name="uq_exams_slug"),
    )