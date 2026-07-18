from pydantic import BaseModel


class BlogBase(BaseModel):
    pass


class BlogCreate(BlogBase):
    pass


class BlogUpdate(BlogBase):
    pass


class BlogResponse(BlogBase):

    id: int

    class Config:
        from_attributes = True
