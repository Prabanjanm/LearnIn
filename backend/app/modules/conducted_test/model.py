import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import BaseModel
from app.core.mixins import StatusMixin

if TYPE_CHECKING:
    from app.modules.conducted_test_paper.model import ConductedTestPaper
    from app.modules.institution.model import Institution, InstitutionUser
    from app.modules.mock_test.model import MockTest


class ConductedTest(
    BaseModel,
    StatusMixin
):
    """
    An institution-scheduled sitting of a fixed question set: a fixed
    server-side time window (scheduled_start_at -> +duration_minutes) that
    every joining student shares, reached only via a shared test_code
    rather than this row's own id. The question set comes from exactly one
    of two sources (see the CheckConstraint below):
      - mock_test_id: an existing, already-published platform MockTest.
      - conducted_test_paper_id: one of this institution's own uploaded
        and confirmed papers (conducted_test_paper/model.py -
        ConductedTestPaper), built via the upload -> process -> review ->
        confirm flow under /institution/conducted-test-papers. That
        content is never mixed into the public Paper/Question tables.

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

    __table_args__ = (
        # Exactly one question source: either an existing platform
        # MockTest, or one of this institution's own uploaded/confirmed
        # ConductedTestPaper (see conducted_test_paper/model.py) - never
        # both, never neither. Enforced at the DB level, not just in
        # service.py, since this is the one invariant every downstream
        # reader (conducted_test_attempt/service.py) depends on to know
        # which question source to load.
        CheckConstraint(
            "(mock_test_id IS NOT NULL) != (conducted_test_paper_id IS NOT NULL)",
            name="ck_conducted_test_exactly_one_source",
        ),
    )

    mock_test_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("mock_tests.id"),
        nullable=True,
        index=True
    )

    conducted_test_paper_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conducted_test_papers.id"),
        nullable=True,
        index=True
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("institutions.id"),
        nullable=False,
        index=True
    )

    created_by_institution_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
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

    mock_test: Mapped["MockTest | None"] = relationship()

    conducted_test_paper: Mapped["ConductedTestPaper | None"] = relationship()

    institution: Mapped["Institution"] = relationship()

    created_by_user: Mapped["InstitutionUser"] = relationship()
