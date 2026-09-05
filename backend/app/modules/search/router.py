from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db

from .schema import SearchResponse
from .service import search_service

router = APIRouter(
    prefix="/api/search",
    tags=["Search"]
)


@router.get("/", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db)
):
    return search_service.search(db, q)
