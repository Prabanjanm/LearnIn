from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import Enum

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.core.enums import StatusEnum
from sqlalchemy import Enum

class SlugMixin:
    """
    SEO Friendly URL
    Example:
        gate
        dbms
        operating-system
    """

    slug: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )


class StatusMixin:
    """
    Common publishing status
    """



status: Mapped[StatusEnum] = mapped_column(
    Enum(
        StatusEnum,
        name="statusenum",
        create_type=False
    ),
    default=StatusEnum.DRAFT,
    nullable=False
)


class SeoMixin:
    """
    Google SEO Fields
    """

    meta_title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    meta_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )