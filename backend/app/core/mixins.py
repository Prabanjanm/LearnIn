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

    Uniqueness is scoped to the parent (e.g. one slug per department),
    not global - each model declares its own UniqueConstraint in
    __table_args__ covering (parent_id, slug). Exam has no parent, so it
    declares UniqueConstraint("slug") for a global scope instead.
    """

    slug: Mapped[str] = mapped_column(
        String(255),
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