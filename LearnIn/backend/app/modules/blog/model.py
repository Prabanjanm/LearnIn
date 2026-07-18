from datetime import date

from sqlalchemy import Date
from sqlalchemy import String
from sqlalchemy import Text

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

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    thumbnail: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    published_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )