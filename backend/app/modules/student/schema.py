import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

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


class StudentVerifyOtp(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)


class StudentResendOtp(BaseModel):
    email: EmailStr


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

    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    avatar_url: str | None = None
    email_verified: bool
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )
