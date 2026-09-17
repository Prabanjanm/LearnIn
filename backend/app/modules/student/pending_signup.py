"""
Signup now verifies the OTP before a Student row ever exists, so there is
no DB row to hang the in-progress signup (hashed password + full name +
OTP hash) off of. Instead it rides along as a short-lived, HttpOnly JWT
cookie scoped to /signup - the same jose/SECRET_KEY machinery as the real
access token, just with its own "purpose" claim so it can never be
mistaken for one.
"""
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.config import settings

PENDING_SIGNUP_COOKIE_NAME = "pending_signup"
_PURPOSE = "student_signup"


def encode_pending_signup(
    email: str,
    hashed_password: str,
    full_name: str | None,
    otp_hash: str,
    ttl_minutes: int,
) -> str:
    payload = {
        "purpose": _PURPOSE,
        "email": email,
        "hashed_password": hashed_password,
        "full_name": full_name,
        "otp_hash": otp_hash,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_pending_signup(token: str | None) -> dict | None:
    if not token:
        return None

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None

    if payload.get("purpose") != _PURPOSE:
        return None

    return payload
