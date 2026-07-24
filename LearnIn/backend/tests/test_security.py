from datetime import timedelta

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_roundtrip():
    hashed = hash_password("s3cret-Pass!")

    assert hashed != "s3cret-Pass!"
    assert verify_password("s3cret-Pass!", hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_roundtrip():
    token = create_access_token(subject="admin@learnin.app")
    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "admin@learnin.app"


def test_expired_token_is_rejected():
    token = create_access_token(
        subject="admin@learnin.app",
        expires_delta=timedelta(seconds=-1),
    )

    assert decode_access_token(token) is None


def test_tampered_token_is_rejected():
    token = create_access_token(subject="admin@learnin.app")

    assert decode_access_token(token + "tampered") is None
