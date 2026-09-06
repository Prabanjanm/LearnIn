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
    id: int
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


class InstitutionUserResponse(BaseModel):
    id: int
    institution_id: int
    email: EmailStr
    full_name: str | None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InstitutionLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
