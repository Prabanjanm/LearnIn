from pydantic import BaseModel, ConfigDict, EmailStr


class AdminLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminResponse(BaseModel):

    id: int
    email: EmailStr
    full_name: str | None = None
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True
    )
