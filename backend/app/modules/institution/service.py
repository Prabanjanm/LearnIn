from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import AlreadyExistsException, InvalidCredentialsException
from app.common.services.base_service import BaseService
from app.common.utils.slug import generate_slug
from app.core.enums import StatusEnum
from app.core.security import hash_password, verify_password

from .model import Institution, InstitutionUser
from .repository import InstitutionRepository, InstitutionUserRepository
from .schema import InstitutionCreate, InstitutionUpdate


class InstitutionService(BaseService):
    """
    Owned/called only by LearnIn Admin routes - an institution never
    manages its own Institution row (name, slug, active status) or its
    own conducted_test_enabled flag; that authority stays platform-side
    per the required ownership model.
    """

    def __init__(self):
        super().__init__(InstitutionRepository())

    def create_institution(self, db: Session, data: InstitutionCreate) -> Institution:
        institution = Institution(
            name=data.name,
            slug=generate_slug(data.name),
            conducted_test_enabled=data.conducted_test_enabled,
            status=StatusEnum.PUBLISHED,
        )
        return self.create(db, institution)

    def update_institution(self, db: Session, institution: Institution, data: InstitutionUpdate) -> Institution:
        updates = data.model_dump(exclude_unset=True)

        if "name" in updates:
            updates.setdefault("slug", generate_slug(updates["name"]))

        for field, value in updates.items():
            setattr(institution, field, value)

        return self.repository.update(db, institution)

    def set_conducted_test_enabled(self, db: Session, institution: Institution, enabled: bool) -> Institution:
        """The server-side switch LearnIn Admin uses to grant/revoke the
        Conducted Test feature for one tenant - this is the ONLY thing
        that authorizes InstitutionService.create() in conducted_test/
        service.py; there is no separate/duplicate permission check."""
        institution.conducted_test_enabled = enabled
        return self.repository.update(db, institution)

    def archive(self, db: Session, institution: Institution) -> Institution:
        institution.status = StatusEnum.ARCHIVED
        return self.repository.update(db, institution)

    def activate(self, db: Session, institution: Institution) -> Institution:
        institution.status = StatusEnum.PUBLISHED
        return self.repository.update(db, institution)


class InstitutionUserService(BaseService):

    def __init__(self):
        super().__init__(InstitutionUserRepository())

    def authenticate(self, db: Session, email: str, password: str) -> InstitutionUser:
        user = self.repository.get_by_email(db, email)

        if not user or not user.is_active:
            raise InvalidCredentialsException("Invalid email or password")

        # An institution deactivated/archived by LearnIn Admin can no
        # longer log in at all, not just lose the Conducted Test feature.
        if user.institution.status == StatusEnum.ARCHIVED:
            raise InvalidCredentialsException("Invalid email or password")

        if not verify_password(password, user.hashed_password):
            raise InvalidCredentialsException("Invalid email or password")

        return user

    def create_institution_user(
        self,
        db: Session,
        institution_id: int,
        email: str,
        password: str,
        full_name: str | None = None,
    ) -> InstitutionUser:
        if self.repository.get_by_email(db, email):
            raise AlreadyExistsException("An institution user with this email already exists")

        user = InstitutionUser(
            institution_id=institution_id,
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
        )
        return self.create(db, user)

    def deactivate(self, db: Session, user: InstitutionUser) -> InstitutionUser:
        user.is_active = False
        user.token_version += 1
        return self.repository.update(db, user)


institution_service = InstitutionService()
institution_user_service = InstitutionUserService()
