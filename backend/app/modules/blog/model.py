from datetime import date

from sqlalchemy import Date
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.core.base import BaseModel
from app.core.mixins import SeoMixin
from app.core.mixins import SlugMixin
from app.core.mixins import StatusMixin


class Blog(
    BaseModel,
    SlugMixin,
    StatusMixin,
    SeoMixin
):

    __tablename__ = "blogs"

    __table_args__ = (
        UniqueConstraint("slug", name="uq_blogs_slug"),
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True
    )

    tags: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    published_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    thumbnail_file_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    thumbnail_mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    thumbnail_file_size: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    thumbnail_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
