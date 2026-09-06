from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import BaseModel


class Admin(BaseModel):
    __tablename__ = "admins"

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

    # See Student.token_version - same "reject tokens signed against a
    # since-changed version" mechanism, kept independent per table so a
    # student password change never affects admin sessions or vice versa.
    token_version: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
