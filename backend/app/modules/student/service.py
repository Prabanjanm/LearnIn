import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import (
    AlreadyExistsException,
    InvalidCredentialsException,
    InvalidStateException,
    NotFoundException,
)
from app.common.services.base_service import BaseService
from app.common.utils.account_lookup import is_email_registered
from app.common.utils.email_templates import otp_verification_email
from app.common.utils.file_tracking import cleanup_drive_file
from app.common.utils.mailer import send_email
from app.core.config import settings
from app.core.security import hash_password, verify_password

from .model import Student
from .pending_signup import decode_pending_signup, encode_pending_signup
from .repository import StudentRepository
from .schema import StudentProfileUpdate

logger = logging.getLogger(__name__)

OTP_LENGTH = 6
OTP_TTL_MINUTES = settings.OTP_EXPIRE_MINUTES


class StudentService(BaseService):

    def __init__(self):
        super().__init__(StudentRepository())

    def authenticate(
        self,
        db: Session,
        email: str,
        password: str
    ) -> Student:

        student = self.repository.get_by_email(db, email)

        if not student or not student.is_active:
            raise InvalidCredentialsException("Invalid email or password")

        if not verify_password(password, student.hashed_password):
            raise InvalidCredentialsException("Invalid email or password")

        return student

    def signup(
        self,
        db: Session,
        email: str,
        password: str,
        full_name: str | None = None
    ) -> Student:

        if is_email_registered(db, email):
            raise AlreadyExistsException("An account with this email already exists")

        student = Student(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
        )

        student = self.repository.create(db, student)
        self._issue_otp(db, student)

        return student

    def initiate_signup(
        self,
        db: Session,
        email: str,
        password: str,
        full_name: str | None = None,
    ) -> str:
        """
        The data-collection-page signup flow: nothing is written to the
        students table yet. The submitted details are hashed and carried in
        a signed, short-lived pending-signup token (see pending_signup.py)
        that the caller sets as a cookie; complete_signup only creates the
        Student row once the OTP that token references comes back correct.
        This is what keeps an abandoned signup from permanently squatting
        on an email address the way the old create-then-verify flow did.
        """
        if is_email_registered(db, email):
            raise AlreadyExistsException("An account with this email already exists")

        otp_code = "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))
        token = encode_pending_signup(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            otp_hash=hash_password(otp_code),
            ttl_minutes=OTP_TTL_MINUTES,
        )

        self._send_otp_email(email, full_name, otp_code)

        return token

    def complete_signup(self, db: Session, token: str | None, otp: str) -> Student:
        payload = decode_pending_signup(token)

        if not payload:
            raise InvalidStateException(
                "Your signup session has expired. Please start again."
            )

        email = payload["email"]

        if is_email_registered(db, email):
            raise AlreadyExistsException("An account with this email already exists")

        if not verify_password(otp, payload["otp_hash"]):
            raise InvalidCredentialsException("Incorrect verification code")

        student = Student(
            email=email,
            hashed_password=payload["hashed_password"],
            full_name=payload.get("full_name"),
            email_verified=True,
        )
        return self.repository.create(db, student)

    def resend_pending_signup_otp(self, db: Session, token: str | None) -> str:
        payload = decode_pending_signup(token)

        if not payload:
            raise InvalidStateException(
                "Your signup session has expired. Please start again."
            )

        email = payload["email"]

        if is_email_registered(db, email):
            raise AlreadyExistsException("An account with this email already exists")

        otp_code = "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))
        new_token = encode_pending_signup(
            email=email,
            hashed_password=payload["hashed_password"],
            full_name=payload.get("full_name"),
            otp_hash=hash_password(otp_code),
            ttl_minutes=OTP_TTL_MINUTES,
        )

        self._send_otp_email(email, payload.get("full_name"), otp_code)

        return new_token

    def _send_otp_email(self, email: str, full_name: str | None, otp_code: str) -> None:
        subject, body = otp_verification_email(full_name, otp_code, OTP_TTL_MINUTES)

        try:
            send_email(to=email, subject=subject, body=body, html=True)
        except Exception:
            logger.exception("Failed to send OTP email to %s", email)

    def _issue_otp(self, db: Session, student: Student) -> None:
        """Generates a fresh OTP, stores only its hash, and emails the
        plaintext code - the same "never persist the secret itself" pattern
        as hashed_password. Failure to send never blocks signup/resend
        itself; the caller already committed the account/OTP hash, and the
        student can always ask for another via resend_otp."""
        otp_code = "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))

        student.otp_hash = hash_password(otp_code)
        student.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)
        self.repository.update(db, student)

        self._send_otp_email(student.email, student.full_name, otp_code)

    def verify_otp(self, db: Session, email: str, otp: str) -> Student:
        student = self.repository.get_by_email(db, email)

        if not student:
            raise NotFoundException("No account found for this email")

        if student.email_verified:
            return student

        if not student.otp_hash or not student.otp_expires_at:
            raise InvalidStateException("No verification code is pending. Request a new one.")

        if datetime.now(timezone.utc) > student.otp_expires_at:
            raise InvalidStateException("This code has expired. Request a new one.")

        if not verify_password(otp, student.otp_hash):
            raise InvalidCredentialsException("Incorrect verification code")

        student.email_verified = True
        student.otp_hash = None
        student.otp_expires_at = None

        return self.repository.update(db, student)

    def resend_otp(self, db: Session, email: str) -> None:
        student = self.repository.get_by_email(db, email)

        if not student:
            raise NotFoundException("No account found for this email")

        if student.email_verified:
            raise InvalidStateException("This email is already verified")

        self._issue_otp(db, student)

    def update_profile(
        self,
        db: Session,
        student: Student,
        data: StudentProfileUpdate,
    ) -> Student:
        student.full_name = data.full_name
        return self.repository.update(db, student)

    def change_password(
        self,
        db: Session,
        student: Student,
        current_password: str,
        new_password: str,
    ) -> Student:
        if not verify_password(current_password, student.hashed_password):
            raise InvalidCredentialsException("Current password is incorrect")

        student.hashed_password = hash_password(new_password)
        # Invalidate every token issued before this change - the old cookie's
        # JWT still carries the previous token_version and will now fail
        # `_resolve_student`'s comparison, even though it hasn't expired yet.
        student.token_version += 1

        return self.repository.update(db, student)

    def set_avatar(
        self,
        db: Session,
        student: Student,
        file_id: str,
    ) -> Student:
        previous_file_id = student.avatar_file_id
        student.avatar_file_id = file_id
        updated = self.repository.update(db, student)

        if previous_file_id and previous_file_id != file_id:
            cleanup_drive_file(db, previous_file_id)

        return updated


student_service = StudentService()
