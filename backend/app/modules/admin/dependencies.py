from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import InvalidCredentialsException
from app.core.database import get_db
from app.core.security import decode_access_token

from .model import Admin
from .repository import AdminRepository

ACCESS_TOKEN_COOKIE_NAME = "access_token"

# auto_error=False so a missing header falls through to the cookie check
# below, instead of the scheme raising 401 on its own.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/login", auto_error=False)

_repository = AdminRepository()


def _resolve_admin(db: Session, token: str | None) -> Admin | None:
    if not token:
        return None

    payload = decode_access_token(token)

    if payload is None or "sub" not in payload or payload.get("type") != "admin":
        return None

    try:
        admin_id = int(payload["sub"])
    except (TypeError, ValueError):
        return None

    admin = _repository.get_by_id(db, admin_id)

    if admin is None or not admin.is_active:
        return None

    if payload.get("tv") != admin.token_version:
        return None

    return admin


def get_current_admin(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Admin:
    """For JSON /api/admin/* routes - Bearer header first, cookie fallback."""

    raw_token = token or request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    admin = _resolve_admin(db, raw_token)

    if admin is None:
        raise InvalidCredentialsException("Could not validate credentials")

    return admin


def get_optional_admin(
    request: Request,
    db: Session = Depends(get_db),
) -> Admin | None:
    """For HTML /admin/* pages - never raises, so routes can redirect to login."""

    raw_token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)

    if not raw_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            raw_token = auth_header[7:]

    return _resolve_admin(db, raw_token)
