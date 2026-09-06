"""
Shared Pydantic field validators, so every schema that accepts a password or
a free-text name enforces the same rule instead of each module inventing its
own (or, as before this file was populated, none at all).
"""

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_NAME_LENGTH = 150


def validate_password_strength(value: str) -> str:
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")

    if len(value) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_LENGTH} characters long.")

    if value.isdigit() or value.isalpha():
        raise ValueError("Password must contain a mix of letters and numbers.")

    return value


def validate_full_name(value: str | None) -> str | None:
    if value is None:
        return value

    value = value.strip()

    if not value:
        return None

    if len(value) > MAX_NAME_LENGTH:
        raise ValueError(f"Name must be at most {MAX_NAME_LENGTH} characters long.")

    return value
