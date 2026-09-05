from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import BaseModel


class Student(BaseModel):
    """
    A logged-in visitor - separate from Admin (which guards the CMS, not
    the public site). Mirrors Admin's shape since the auth mechanics are
    identical (bcrypt + JWT cookie), just a different cookie name so a
    student and admin session in the same browser don't collide.
    """

    __tablename__ = "students"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    full_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
