from pydantic import BaseModel


class DepartmentCreate(BaseModel):
    exam_id: int
    name: str
    code: str
    display_order: int = 0