from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from .schema import DepartmentCreate
from .service import department_service

router = APIRouter(
    prefix="/api/departments",
    tags=["Departments"]
)


@router.get("/")
def get_all(
    exam_id: int,
    db: Session = Depends(get_db)
):
    return department_service.get_by_exam(
        db,
        exam_id
    )


@router.post("/")
def create(
    data: DepartmentCreate,
    db: Session = Depends(get_db)
):
    return department_service.create_department(
        db,
        data
    )