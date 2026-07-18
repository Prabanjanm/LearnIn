from pydantic import BaseModel


class MockTestBase(BaseModel):
    pass


class MockTestCreate(MockTestBase):
    pass


class MockTestUpdate(MockTestBase):
    pass


class MockTestResponse(MockTestBase):

    id: int

    class Config:
        from_attributes = True
