from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import InvalidCredentialsException
from app.core.database import get_db
from app.core.security import decode_access_token

from .model import InstitutionUser
from .repository import InstitutionUserRepository

INSTITUTION_ACCESS_TOKEN_COOKIE_NAME = "institution_access_token"

# auto_error=False so a missing header falls through to the cookie check
# below, instead of the scheme raising 401 on its own.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/institution/login", auto_error=False)

_repository = InstitutionUserRepository()


def _resolve_institution_user(db: Session, token: str | None) -> InstitutionUser | None:
    if not token:
        return None

    payload = decode_access_token(token)

    # "institution_user" is its own distinct token "type" - a Student or
    # Admin JWT (even a validly-signed one) is never accepted here, and
    # this token is never accepted by get_current_student/get_current_admin.
    if payload is None or "sub" not in payload or payload.get("type") != "institution_user":
        return None

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        return None

    user = _repository.get_by_id(db, user_id)

    if user is None or not user.is_active:
        return None

    if payload.get("tv") != user.token_version:
        return None

    return user


def get_current_institution_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> InstitutionUser:
    """For JSON /api/institution/* routes that require a logged-in
    institution user - Bearer header first, cookie fallback."""

    raw_token = token or request.cookies.get(INSTITUTION_ACCESS_TOKEN_COOKIE_NAME)
    user = _resolve_institution_user(db, raw_token)

    if user is None:
        raise InvalidCredentialsException("Could not validate credentials")

    return user


def get_optional_institution_user(
    request: Request,
    db: Session = Depends(get_db),
) -> InstitutionUser | None:
    """For HTML /institution/* pages - never raises, so routes can redirect to login."""

    raw_token = request.cookies.get(INSTITUTION_ACCESS_TOKEN_COOKIE_NAME)

    if not raw_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            raw_token = auth_header[7:]

    return _resolve_institution_user(db, raw_token)
