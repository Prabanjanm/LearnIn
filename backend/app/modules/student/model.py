from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
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

    avatar_file_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    # Bumped on password change (and available for a future admin-initiated
    # "log out everywhere" action). Every issued JWT carries the value it was
    # signed with ("tv" claim) - a mismatch against the current DB value means
    # the token predates a security-relevant change and is rejected even
    # though it hasn't expired yet. This is what actually invalidates a
    # leaked/old token on password change, since deleting a cookie alone
    # can't touch a copy of the token elsewhere.
    token_version: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    # Signup sends an OTP by email; nothing currently gates login on this
    # (see StudentService.signup/verify_otp) - it just tracks whether the
    # address has been confirmed.
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    # Only ever a bcrypt hash of the current 6-digit code, never the code
    # itself - same reasoning as hashed_password. NULL once verified/unused.
    otp_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    otp_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    @property
    def avatar_url(self) -> str | None:
        """Derived on demand from the Drive file id, never stored. Unlike
        every other entity's Drive files (which are intentionally public),
        an avatar is uploaded non-public and only ever served through our
        own authenticated /media/{file_id} endpoint (see
        app/modules/media) - so this returns a same-origin path, not a
        direct Drive link. Read by both templates (direct attribute access)
        and StudentResponse (from_attributes)."""
        if not self.avatar_file_id:
            return None
        return f"/media/{self.avatar_file_id}"
