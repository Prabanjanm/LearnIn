import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.enums import StatusEnum


class InstitutionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    conducted_test_enabled: bool = False


class InstitutionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    conducted_test_enabled: bool | None = None
    status: StatusEnum | None = None


class InstitutionResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    conducted_test_enabled: bool
    status: StatusEnum
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InstitutionUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = None
    phone: str | None = None


class InstitutionUserResponse(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    email: EmailStr
    full_name: str | None
    phone: str | None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InstitutionLogin(BaseModel):
    email: EmailStr
    password: str


class InstitutionSignupRequest(BaseModel):
    """
    Public self-signup for a new Institution. Unlike InstitutionUserCreate
    (an admin adding a user to an institution that already exists and is
    already approved), this creates BOTH a new Institution (status=DRAFT,
    invisible/unusable until an admin approves it) and its first user.

    phone is required (unlike InstitutionUserCreate's optional one) - it's
    the anti-spam signal that lets the reviewing admin actually verify a
    new tenant request is a real institution before approving it.
    """
    institution_name: str = Field(min_length=1, max_length=255)
    contact_name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=20)
    password: str = Field(min_length=8, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
