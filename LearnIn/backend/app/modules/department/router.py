from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin.dependencies import get_current_admin
from .schema import DepartmentCreate, DepartmentResponse
from .service import department_service

router = APIRouter(
    prefix="/api/departments",
    tags=["Departments"]
)


@router.get("/", response_model=list[DepartmentResponse])
def get_all(
    exam_id: int,
    db: Session = Depends(get_db)
):
    return department_service.get_published_by_exam(
        db,
        exam_id
    )


@router.get("/{department_id}", response_model=DepartmentResponse)
def get_one(
    department_id: int,
    db: Session = Depends(get_db)
):
    return department_service.get_published_by_id(db, department_id)


@router.post("/", response_model=DepartmentResponse)
def create(
    data: DepartmentCreate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return department_service.create_department(
        db,
        data
    )