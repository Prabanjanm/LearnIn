from sqlalchemy.orm import Session, selectinload

from app.common.repositories.base_repository import BaseRepository
from app.core.enums import StatusEnum

from .model import ConductedTest


class ConductedTestRepository(BaseRepository):

    def __init__(self):
        super().__init__(ConductedTest)

    def get_by_code(self, db: Session, test_code: str) -> ConductedTest | None:
        return (
            db.query(ConductedTest)
            .options(selectinload(ConductedTest.mock_test))
            .filter(ConductedTest.test_code == test_code.strip().upper())
            .filter(ConductedTest.status != StatusEnum.ARCHIVED)
            .first()
        )

    def code_exists(self, db: Session, test_code: str) -> bool:
        return db.query(ConductedTest).filter(ConductedTest.test_code == test_code).first() is not None

    def get_by_institution(self, db: Session, institution_id: int) -> list[ConductedTest]:
        """The multi-tenant scoping query - every listing/lookup an
        institution portal route uses ultimately goes through this or
        get_by_id_for_institution, never an unscoped get_by_id."""
        return (
            db.query(ConductedTest)
            .filter(
                ConductedTest.institution_id == institution_id,
                ConductedTest.status != StatusEnum.ARCHIVED,
            )
            .order_by(ConductedTest.created_at.desc())
            .all()
        )

    def get_by_id_for_institution(self, db: Session, conducted_test_id: int, institution_id: int) -> ConductedTest | None:
        return (
            db.query(ConductedTest)
            .filter(
                ConductedTest.id == conducted_test_id,
                ConductedTest.institution_id == institution_id,
            )
            .first()
        )
