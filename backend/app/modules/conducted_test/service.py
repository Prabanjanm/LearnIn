import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import ForbiddenException, InvalidStateException, NotFoundException
from app.common.services.base_service import BaseService
from app.core.enums import StatusEnum
from app.modules.institution.model import InstitutionUser
from app.modules.mock_test.service import mock_test_service

from .model import ConductedTest
from .repository import ConductedTestRepository
from .schema import ConductedTestCreate, ConductedTestUpdate

# Excludes visually-confusable characters (0/O, 1/I) so a code read aloud
# or handwritten on a whiteboard is never ambiguous.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_LENGTH = 5


class ConductedTestService(BaseService):

    def __init__(self):
        super().__init__(ConductedTestRepository())

    # ------------------------------------------------------------ auth --

    @staticmethod
    def _require_can_create(institution_user: InstitutionUser) -> None:
        """Server-side gate for the whole feature - a normal student never
        reaches this (these routes all require get_current_institution_user
        first), and even a logged-in institution user is rejected here if
        LearnIn Admin has not enabled Conducted Tests for their
        institution - never just a hidden menu item in the frontend."""
        institution = institution_user.institution
        if institution.status == StatusEnum.ARCHIVED:
            raise ForbiddenException("Your institution's account is not active")
        if not institution.conducted_test_enabled:
            raise ForbiddenException("Your institution is not authorized to create conducted tests")

    # -------------------------------------------------------- creation --

    def generate_unique_code(self, db: Session) -> str:
        for _ in range(20):
            candidate = "LIN-" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
            if not self.repository.code_exists(db, candidate):
                return candidate
        # Astronomically unlikely with a 32^5 keyspace at this table size,
        # but never loop forever - surface a clear error instead of hanging.
        raise InvalidStateException("Could not generate a unique test code, please try again")

    def create(self, db: Session, institution_user: InstitutionUser, data: ConductedTestCreate) -> ConductedTest:
        self._require_can_create(institution_user)

        # Must reference a real, already-published MockTest - raises
        # NotFoundException otherwise. This is the "select an existing
        # LearnIn Mock Test" path; a brand-new paper is created via the
        # existing admin Paper/Question/MockTest flow first, then selected
        # here by id, so this never duplicates the question engine.
        mock_test_service.get_published_by_id(db, data.mock_test_id)

        conducted_test = ConductedTest(
            mock_test_id=data.mock_test_id,
            institution_id=institution_user.institution_id,
            created_by_institution_user_id=institution_user.id,
            title=data.title,
            instructions=data.instructions,
            test_code=self.generate_unique_code(db),
            duration_minutes=data.duration_minutes,
            scheduled_start_at=data.scheduled_start_at,
            status=StatusEnum.DRAFT,
        )
        return super().create(db, conducted_test)

    # ------------------------------------------------------- retrieval --

    def get_for_manage(self, db: Session, conducted_test_id: int, institution_user: InstitutionUser) -> ConductedTest:
        """Scoped at the query level (not just a Python-side id comparison
        after an unscoped fetch) - a conducted test belonging to a
        different institution is indistinguishable from one that doesn't
        exist at all, both here and to the caller (404 either way)."""
        conducted_test = self.repository.get_by_id_for_institution(
            db, conducted_test_id, institution_user.institution_id
        )
        if conducted_test is None:
            raise NotFoundException("Conducted test not found")
        return conducted_test

    def list_for_institution(self, db: Session, institution_user: InstitutionUser) -> list[ConductedTest]:
        return self.repository.get_by_institution(db, institution_user.institution_id)

    def get_by_code_for_join(self, db: Session, test_code: str) -> ConductedTest:
        conducted_test = self.repository.get_by_code(db, test_code)
        if conducted_test is None or conducted_test.status != StatusEnum.PUBLISHED:
            # Same generic message either way - never reveal whether a
            # code exists but is merely inactive/archived vs. not existing
            # at all.
            raise NotFoundException("Invalid or inactive test code")
        return conducted_test

    # --------------------------------------------------------- mutate --

    def update(
        self,
        db: Session,
        institution_user: InstitutionUser,
        conducted_test_id: int,
        data: ConductedTestUpdate,
    ) -> ConductedTest:
        conducted_test = self.get_for_manage(db, conducted_test_id, institution_user)
        self._require_not_started(conducted_test)

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(conducted_test, field, value)

        return self.repository.update(db, conducted_test)

    def activate(self, db: Session, institution_user: InstitutionUser, conducted_test_id: int) -> ConductedTest:
        conducted_test = self.get_for_manage(db, conducted_test_id, institution_user)
        conducted_test.status = StatusEnum.PUBLISHED
        return self.repository.update(db, conducted_test)

    def deactivate(self, db: Session, institution_user: InstitutionUser, conducted_test_id: int) -> ConductedTest:
        conducted_test = self.get_for_manage(db, conducted_test_id, institution_user)
        conducted_test.status = StatusEnum.DRAFT
        return self.repository.update(db, conducted_test)

    def soft_delete(self, db: Session, institution_user: InstitutionUser, conducted_test_id: int) -> ConductedTest:
        """Archives rather than deletes - same lifecycle mechanism the rest
        of the admin panel already uses for exams/departments/subjects.
        Attempts/results already recorded are never touched, so historical
        results survive archiving the test itself."""
        conducted_test = self.get_for_manage(db, conducted_test_id, institution_user)
        conducted_test.status = StatusEnum.ARCHIVED
        return self.repository.update(db, conducted_test)

    @staticmethod
    def _require_not_started(conducted_test: ConductedTest) -> None:
        if datetime.now(timezone.utc) >= conducted_test.scheduled_start_at:
            raise InvalidStateException(
                "This test's scheduled window has already started and can no longer be edited"
            )

    @staticmethod
    def window(conducted_test: ConductedTest) -> tuple[datetime, datetime]:
        # scheduled_start_at is always written as a UTC-aware datetime (see
        # create()); SQLite (used only in tests - Postgres in production
        # preserves the offset natively) drops the tzinfo on round-trip, so
        # a naive value read back is always re-interpreted as UTC rather
        # than compared against an aware "now" and raising TypeError.
        start = conducted_test.scheduled_start_at
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        end = start + timedelta(minutes=conducted_test.duration_minutes)
        return start, end


conducted_test_service = ConductedTestService()
