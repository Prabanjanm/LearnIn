from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import BaseModel
from app.core.mixins import StatusMixin

if TYPE_CHECKING:
    from app.modules.institution.model import Institution, InstitutionUser
    from app.modules.mock_test.model import MockTest


class ConductedTest(
    BaseModel,
    StatusMixin
):
    """
    An institution-scheduled sitting of an existing MockTest: a fixed
    server-side time window (scheduled_start_at -> +duration_minutes) that
    every joining student shares, reached only via a shared test_code
    rather than this row's own id. Deliberately does not duplicate the
    question engine - it always points at an existing, already-published
    MockTest (see mock_test_id); "upload a new paper" is the existing
    admin Paper/Question/MockTest creation flow, done first, with the
    resulting MockTest then selected here.

    Owned by an Institution (a tenant), not by LearnIn Admin -
    institution_id is the multi-tenant scoping key every query in
    conducted_test/repository.py and conducted_test/service.py must
    filter by. created_by_institution_user_id records which specific
    login within that institution created it, for audit purposes only -
    ownership/authorization is always checked against institution_id,
    never against the individual user id, so any user belonging to the
    owning institution can manage a test a colleague created.

    Reuses the project's one lifecycle mechanism (StatusMixin) instead of
    a second soft-delete system: DRAFT = created but not yet shared,
    PUBLISHED = active/joinable, ARCHIVED = soft-deleted (never a hard
    delete - see conducted_test/service.py).
    """

    __tablename__ = "conducted_tests"

    mock_test_id: Mapped[int] = mapped_column(
        ForeignKey("mock_tests.id"),
        nullable=False,
        index=True
    )

    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id"),
        nullable=False,
        index=True
    )

    created_by_institution_user_id: Mapped[int] = mapped_column(
        ForeignKey("institution_users.id"),
        nullable=False,
        index=True
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    instructions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # e.g. "LIN-G8K42" - cryptographically random (see
    # conducted_test/service.py::generate_test_code), never a sequential/
    # guessable database id. Case-insensitive lookups only (see
    # repository.get_by_code) - always stored upper-cased.
    test_code: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True
    )

    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    scheduled_start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    mock_test: Mapped["MockTest"] = relationship()

    institution: Mapped["Institution"] = relationship()

    created_by_user: Mapped["InstitutionUser"] = relationship()
