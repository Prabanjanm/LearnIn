from pydantic import BaseModel


class NoteBase(BaseModel):
    pass


class NoteCreate(NoteBase):
    pass


class NoteUpdate(NoteBase):
    pass


class NoteResponse(NoteBase):

    id: int

    class Config:
        from_attributes = True
