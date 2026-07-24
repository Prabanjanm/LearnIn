from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin.dependencies import get_current_admin

from .schema import ResourceCreate, ResourceResponse
from .service import resource_service

router = APIRouter(
    prefix="/api/resources",
    tags=["Resources"]
)


@router.get("/", response_model=list[ResourceResponse])
def get_all(
    subject_id: int,
    db: Session = Depends(get_db)
):
    return resource_service.get_published_by_subject(db, subject_id)


@router.get("/{resource_id}", response_model=ResourceResponse)
def get_one(
    resource_id: int,
    db: Session = Depends(get_db)
):
    return resource_service.get_published_by_id(db, resource_id)


@router.post("/", response_model=ResourceResponse)
def create(
    data: ResourceCreate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return resource_service.create_resource(db, data)
