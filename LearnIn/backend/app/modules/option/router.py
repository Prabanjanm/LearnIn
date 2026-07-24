from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin.dependencies import get_current_admin

from .schema import OptionCreate, OptionResponse
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
