from pydantic import BaseModel


class PaperBase(BaseModel):
    pass


class PaperCreate(PaperBase):
    pass


class PaperUpdate(PaperBase):
    pass


class PaperResponse(PaperBase):

    id: int

    class Config:
        from_attributes = True
