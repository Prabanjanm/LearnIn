from sqlalchemy.orm import Session

from app.common.repositories.base_repository import BaseRepository
from app.core.enums import StatusEnum

from .model import Institution, InstitutionUser


class InstitutionRepository(BaseRepository):

    def __init__(self):
        super().__init__(Institution)

    def get_by_slug(self, db: Session, slug: str) -> Institution | None:
        return db.query(Institution).filter(Institution.slug == slug).first()

    def get_active(self, db: Session) -> list[Institution]:
        return (
            db.query(Institution)
            .filter(Institution.status != StatusEnum.ARCHIVED)
            .order_by(Institution.name.asc())
            .all()
        )


class InstitutionUserRepository(BaseRepository):

    def __init__(self):
        super().__init__(InstitutionUser)

    def get_by_email(self, db: Session, email: str) -> InstitutionUser | None:
        return db.query(InstitutionUser).filter(InstitutionUser.email == email).first()

    def get_by_institution(self, db: Session, institution_id: int) -> list[InstitutionUser]:
        return (
            db.query(InstitutionUser)
            .filter(InstitutionUser.institution_id == institution_id)
            .order_by(InstitutionUser.created_at.desc())
            .all()
        )
