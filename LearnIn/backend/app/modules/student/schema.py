from pydantic import BaseModel, ConfigDict, EmailStr


class StudentSignup(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class StudentLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class StudentResponse(BaseModel):

    id: int
    email: EmailStr
    full_name: str | None = None

    model_config = ConfigDict(
        from_attributes=True
    )
