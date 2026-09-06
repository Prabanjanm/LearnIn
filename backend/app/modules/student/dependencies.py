from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import InvalidCredentialsException
from app.core.database import get_db
from app.core.security import decode_access_token

from .model import Student
from .repository import StudentRepository

STUDENT_ACCESS_TOKEN_COOKIE_NAME = "student_access_token"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/students/login", auto_error=False)

_repository = StudentRepository()


def _resolve_student(db: Session, token: str | None) -> Student | None:
    if not token:
        return None

    payload = decode_access_token(token)

    if payload is None or "sub" not in payload or payload.get("type") != "student":
        return None

    try:
        student_id = int(payload["sub"])
    except (TypeError, ValueError):
        return None

    student = _repository.get_by_id(db, student_id)

    if student is None or not student.is_active:
        return None

    if payload.get("tv") != student.token_version:
        return None

    return student


def get_current_student(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Student:
    """For JSON endpoints that require a logged-in student."""

    raw_token = token or request.cookies.get(STUDENT_ACCESS_TOKEN_COOKIE_NAME)
    student = _resolve_student(db, raw_token)

    if student is None:
        raise InvalidCredentialsException("Could not validate credentials")

    return student


def get_optional_student(
    request: Request,
    db: Session = Depends(get_db),
) -> Student | None:
    """For public HTML pages - never raises, so pages can render either way."""

    raw_token = request.cookies.get(STUDENT_ACCESS_TOKEN_COOKIE_NAME)
    return _resolve_student(db, raw_token)
