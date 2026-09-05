from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin.dependencies import get_current_admin

from .schema import DepartmentCreate, DepartmentResponse, DepartmentUpdate
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
    return department_service.get_published_by_exam(db, exam_id)


@router.get("/{exam_id}/{slug}", response_model=DepartmentResponse)
def get_one(
    exam_id: int,
    slug: str,
    db: Session = Depends(get_db)
):
    return department_service.get_published_by_slug(db, exam_id, slug)


@router.post("/", response_model=DepartmentResponse)
def create(
    data: DepartmentCreate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return department_service.create_department(db, data)


@router.patch("/{department_id}", response_model=DepartmentResponse)
def update(
    department_id: int,
    data: DepartmentUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    department = department_service.get_or_404(db, department_id, "Department not found")
    return department_service.update_department(db, department, data)


@router.delete("/{department_id}", status_code=204)
def delete(
    department_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    department = department_service.get_or_404(db, department_id, "Department not found")
    department_service.delete_department(db, department)
