from pydantic import BaseModel


class SubjectBase(BaseModel):
    pass


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(SubjectBase):
    pass


class SubjectResponse(SubjectBase):

    id: int

    class Config:
        from_attributes = True
