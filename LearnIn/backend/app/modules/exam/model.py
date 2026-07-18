from typing import TYPE_CHECKING

from sqlalchemy import String, Text
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

    icon: Mapped[str | None] = mapped_column(String(255), nullable=True)

    display_order: Mapped[int] = mapped_column(default=0)

    # ✅ INSIDE the class
    departments: Mapped[list["Department"]] = relationship(
        back_populates="exam",
        cascade="all, delete-orphan"
    )