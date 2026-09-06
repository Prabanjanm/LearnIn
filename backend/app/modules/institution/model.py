from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import BaseModel
from app.core.mixins import SlugMixin, StatusMixin

if TYPE_CHECKING:
    pass


class Institution(
    BaseModel,
    SlugMixin,
    StatusMixin
):
    """
    A tenant organization (a college/coaching institute) that can run its
    own Conducted Tests, completely isolated from every other institution.
    LearnIn Admin creates/manages this row and its feature flags; an
    institution never manages itself here - it only manages its own
    ConductedTests through its own portal (see app/modules/institution/
    router.py + pages.py), scoped by institution_id everywhere.

    Reuses the project's one lifecycle mechanism (StatusMixin) for
    enable/disable-the-whole-institution: PUBLISHED = active, ARCHIVED =
    deactivated/soft-deleted. conducted_test_enabled is a separate,
    narrower flag - the same simple boolean-permission pattern already
    used for Admin.can_create_conducted_test (now removed from Admin and
    reintroduced here, on the tenant, per the corrected ownership model) -
    "is this institution allowed to use the Conducted Test feature at
    all," independent of whether the institution itself is active.
    """

    __tablename__ = "institutions"

    __table_args__ = (
        UniqueConstraint("name", name="uq_institutions_name"),
        UniqueConstraint("slug", name="uq_institutions_slug"),
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    conducted_test_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    users: Mapped[list["InstitutionUser"]] = relationship(
        back_populates="institution",
        cascade="all, delete-orphan",
    )


class InstitutionUser(BaseModel):
    """
    A login-capable account belonging to one Institution - mirrors
    Admin/Student's auth shape exactly (bcrypt + JWT cookie, own
    token_version for revocation-on-password-change), with its own cookie
    name/token "type" so an institution session can never be resolved as
    a Student or Admin session and vice versa. This is the "distinct
    Institution role/context" the multi-tenant design requires - never
    treated as a Student, never treated as a LearnIn Admin.
    """

    __tablename__ = "institution_users"

    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id"),
        nullable=False,
        index=True
    )

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

    token_version: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    institution: Mapped["Institution"] = relationship(back_populates="users")
