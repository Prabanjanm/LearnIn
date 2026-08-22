from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import StatusEnum
from app.modules.admin.dependencies import get_current_admin

from .schema import ResourceCreate, ResourceResponse, ResourceUpdate
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


@router.patch("/{resource_id}", response_model=ResourceResponse)
def update(
    resource_id: int,
    data: ResourceUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    resource = resource_service.get_or_404(db, resource_id, "Resource not found")
    return resource_service.update_resource(db, resource, data)


@router.post("/{resource_id}/publish", response_model=ResourceResponse)
def publish(
    resource_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    resource = resource_service.get_or_404(db, resource_id, "Resource not found")
    return resource_service.update_resource(db, resource, ResourceUpdate(status=StatusEnum.PUBLISHED))


@router.post("/{resource_id}/archive", response_model=ResourceResponse)
def archive(
    resource_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    resource = resource_service.get_or_404(db, resource_id, "Resource not found")
    return resource_service.update_resource(db, resource, ResourceUpdate(status=StatusEnum.ARCHIVED))


@router.delete("/{resource_id}", status_code=204)
def delete(
    resource_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    resource = resource_service.get_or_404(db, resource_id, "Resource not found")
    resource_service.delete_resource(db, resource)
