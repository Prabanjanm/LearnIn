from pydantic import BaseModel, ConfigDict


class ExamBase(BaseModel):
    name: str
    code: str
    slug: str
    description: str | None = None
    icon: str | None = None
    display_order: int = 0


class ExamCreate(ExamBase):
    pass


class ExamUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    slug: str | None = None
    description: str | None = None
    icon: str | None = None
    display_order: int | None = None


class ExamResponse(ExamBase):

    id: int

    model_config = ConfigDict(
        from_attributes=True
    )