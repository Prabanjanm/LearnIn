from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin.dependencies import get_current_admin

from .schema import PaperCreate, PaperResponse
from .service import paper_service

router = APIRouter(
    prefix="/api/papers",
    tags=["Papers"]
)


@router.get("/", response_model=list[PaperResponse])
def get_all(
    subject_id: int,
    db: Session = Depends(get_db)
):
    return paper_service.get_published_by_subject(db, subject_id)


@router.get("/{paper_id}", response_model=PaperResponse)
def get_one(
    paper_id: int,
    db: Session = Depends(get_db)
):
    return paper_service.get_published_by_id(db, paper_id)


@router.post("/", response_model=PaperResponse)
def create(
    data: PaperCreate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return paper_service.create_paper(db, data)
