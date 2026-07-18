from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import Text

from sqlalchemy.orm import Mapped, relationship
from sqlalchemy.orm import mapped_column

from app.core.base import BaseModel
from app.core.enums import ResourceType
from app.core.mixins import StatusMixin


class Resource(
    BaseModel,
    StatusMixin
):

    __tablename__ = "resources"

    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"),
        nullable=False,
        index=True
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    resource_type: Mapped[ResourceType] = mapped_column(
        Enum(ResourceType, name="resourcetype"),
        nullable=False
    )

    google_drive_file_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    subject = relationship(
    "Subject",
    back_populates="resources"
)