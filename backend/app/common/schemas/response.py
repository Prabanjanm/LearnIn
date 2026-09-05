from pydantic import BaseModel


class ApiResponse(BaseModel):
    success: bool
    message: str
    data: object | None = None