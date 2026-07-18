from pydantic import BaseModel


class QuestionBase(BaseModel):
    pass


class QuestionCreate(QuestionBase):
    pass


class QuestionUpdate(QuestionBase):
    pass


class QuestionResponse(QuestionBase):

    id: int

    class Config:
        from_attributes = True
