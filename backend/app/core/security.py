from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: str,
    token_type: str,
    token_version: int = 0,
    expires_delta: timedelta | None = None
) -> str:
    """
    `subject` is always a stable numeric id (as a string) - never email -
    so changing a user's email can't invalidate their session and a client
    can never influence what ends up in the token. `token_type` ("student"
    or "admin") and `token_version` are checked by the resolving dependency
    so a token can't be replayed against the wrong user table and a
    password change (which bumps token_version) invalidates every
    previously-issued token immediately, not just at its natural expiry.
    """

    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload = {
        "sub": subject,
        "type": token_type,
        "tv": token_version,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError:
        return None
