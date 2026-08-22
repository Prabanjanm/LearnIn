from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin.dependencies import get_current_admin

from .schema import OptionCreate, OptionResponse, OptionUpdate
from .service import option_service

router = APIRouter(
    prefix="/api/options",
    tags=["Options"]
)


@router.get("/", response_model=list[OptionResponse])
def get_all(
    question_id: int,
    db: Session = Depends(get_db)
):
    return option_service.get_by_question(db, question_id)


@router.post("/", response_model=OptionResponse)
def create(
    data: OptionCreate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return option_service.create_option(db, data)


@router.patch("/{option_id}", response_model=OptionResponse)
def update(
    option_id: int,
    data: OptionUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    option = option_service.get_or_404(db, option_id, "Option not found")
    return option_service.update_option(db, option, data)


@router.delete("/{option_id}", status_code=204)
def delete(
    option_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    option = option_service.get_or_404(db, option_id, "Option not found")
    option_service.delete_option(db, option)
