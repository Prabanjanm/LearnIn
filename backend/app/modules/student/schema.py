from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.common.validators import validate_full_name, validate_password_strength


class StudentSignup(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None

    _validate_password = field_validator("password")(validate_password_strength)
    _validate_full_name = field_validator("full_name")(validate_full_name)


class StudentLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class StudentProfileUpdate(BaseModel):
    full_name: str | None = None

    _validate_full_name = field_validator("full_name")(validate_full_name)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    _validate_new_password = field_validator("new_password")(validate_password_strength)


class StudentResponse(BaseModel):

    id: int
    email: EmailStr
    full_name: str | None = None
    avatar_url: str | None = None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )
