import logging
import uuid

from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import AlreadyExistsException, InvalidCredentialsException
from app.common.services.base_service import BaseService
from app.common.utils.email_templates import (
    institution_request_confirmation_email,
    institution_status_update_email,
)
from app.common.utils.mailer import send_email
from app.common.utils.slug import generate_slug
from app.core.enums import StatusEnum
from app.core.security import hash_password, verify_password

logger = logging.getLogger(__name__)


def _primary_contact(institution: "Institution") -> "InstitutionUser | None":
    """The user who submitted the self-signup request - same "earliest
    user" convention already used by admin_pages.py's requesting_user."""
    return min(institution.users, key=lambda u: u.created_at, default=None)


def _notify(to: str, subject: str, body: str) -> None:
    # Institution approval/rejection must never fail because the mail relay
    # is down - log and move on, the status change itself already committed.
    try:
        send_email(to=to, subject=subject, body=body, html=True)
    except Exception:
        logger.exception("Failed to send notification email to %s", to)

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

    def create_pending_institution(self, db: Session, name: str) -> Institution:
        """
        A self-signed-up institution starts DRAFT - the same "not visible/
        usable yet" status every other publishable entity in this codebase
        uses - rather than PUBLISHED like an admin-created one, so it can't
        log in or appear anywhere until an admin reviews and activates it
        (see InstitutionUserService.authenticate).
        """
        institution = Institution(
            name=name,
            slug=generate_slug(name),
            conducted_test_enabled=False,
            status=StatusEnum.DRAFT,
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
        updated = self.repository.update(db, institution)

        contact = _primary_contact(updated)
        if contact:
            subject, body = institution_status_update_email(
                updated.name, contact.full_name, approved=False
            )
            _notify(contact.email, subject, body)

        return updated

    def activate(self, db: Session, institution: Institution) -> Institution:
        institution.status = StatusEnum.PUBLISHED
        updated = self.repository.update(db, institution)

        contact = _primary_contact(updated)
        if contact:
            subject, body = institution_status_update_email(
                updated.name, contact.full_name, approved=True
            )
            _notify(contact.email, subject, body)

        return updated


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

        # Checked only after the password is verified, so a wrong-password
        # guess never reveals whether an institution is pending vs archived.
        if user.institution.status == StatusEnum.DRAFT:
            raise InvalidCredentialsException(
                "This institution's signup request is still awaiting admin approval."
            )

        return user

    def create_institution_user(
        self,
        db: Session,
        institution_id: uuid.UUID,
        email: str,
        password: str,
        full_name: str | None = None,
        phone: str | None = None,
    ) -> InstitutionUser:
        if self.repository.get_by_email(db, email):
            raise AlreadyExistsException("An institution user with this email already exists")

        user = InstitutionUser(
            institution_id=institution_id,
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            phone=phone,
        )
        return self.create(db, user)

    def deactivate(self, db: Session, user: InstitutionUser) -> InstitutionUser:
        user.is_active = False
        user.token_version += 1
        return self.repository.update(db, user)


institution_service = InstitutionService()
institution_user_service = InstitutionUserService()


def request_institution_signup(
    db: Session,
    institution_name: str,
    contact_name: str,
    email: str,
    phone: str,
    password: str,
) -> InstitutionUser:
    """
    Public self-signup entry point: creates a DRAFT (pending) Institution
    plus its first user in one step. Checked here rather than only relying
    on create_institution_user's own check, so a duplicate email fails
    before a throwaway Institution row is created for nothing.
    """
    if institution_user_service.repository.get_by_email(db, email):
        raise AlreadyExistsException("An account with this email already exists")

    institution = institution_service.create_pending_institution(db, institution_name)

    user = institution_user_service.create_institution_user(
        db, institution.id, email, password, contact_name, phone
    )

    subject, body = institution_request_confirmation_email(institution_name, contact_name)
    _notify(email, subject, body)

    return user
