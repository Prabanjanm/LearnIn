import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import GoogleDriveConfigError
from app.common.utils.file_tracking import is_file_referenced
from app.core.database import get_db
from app.core.google_drive import get_drive_client
from app.modules.admin.dependencies import get_current_admin

from .schema import PaperCreate, PaperResponse, PaperUpdate
from .service import paper_service

router = APIRouter(
    prefix="/api/papers",
    tags=["Papers"]
)

logger = logging.getLogger(__name__)


@router.get("/", response_model=list[PaperResponse])
def get_all(
    subject_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    return paper_service.get_published_by_subject(db, subject_id)


@router.get("/files/{file_id}/stream")
def stream_file(
    file_id: str,
    db: Session = Depends(get_db),
):
    """
    Proxies a Drive file's bytes through our own backend, inline (not as an
    attachment), so a question/answer paper can be embedded in our own
    viewer page instead of linking out to Drive's viewer - which some Drive
    accounts/files refuse to render in an iframe ("This content is blocked").

    Public (no admin auth) since papers are viewed by students, but still
    gated by is_file_referenced so only file ids LearnIn actually tracks
    (question/answer papers, resources, etc.) can be pulled through this
    proxy - not arbitrary files the connected Drive account can see.
    """
    if not is_file_referenced(db, file_id):
        raise HTTPException(status_code=404, detail="File not found")

    client = get_drive_client()

    try:
        metadata = client.get_file_metadata(file_id)
        content = client.download_file(file_id)
    except GoogleDriveConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        logger.exception("Failed to download Drive file %s", file_id)
        raise HTTPException(status_code=502, detail="Failed to download file from Drive")

    mime_type = metadata.get("mimeType") or "application/octet-stream"

    return Response(
        content=content,
        media_type=mime_type,
        headers={"Content-Disposition": "inline"},
    )


@router.get("/{paper_id}", response_model=PaperResponse)
def get_by_id(
    paper_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    return paper_service.get_published_by_id(db, paper_id)


@router.get("/{subject_id}/{year}", response_model=PaperResponse)
def get_one(
    subject_id: uuid.UUID,
    year: int,
    db: Session = Depends(get_db)
):
    return paper_service.get_published_by_year(db, subject_id, year)


@router.post("/", response_model=PaperResponse)
def create(
    data: PaperCreate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return paper_service.create_paper(db, data)


@router.patch("/{paper_id}", response_model=PaperResponse)
def update(
    paper_id: uuid.UUID,
    data: PaperUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    paper = paper_service.get_or_404(db, paper_id, "Paper not found")
    return paper_service.update_paper(db, paper, data)


@router.delete("/{paper_id}", status_code=204)
def delete(
    paper_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    paper = paper_service.get_or_404(db, paper_id, "Paper not found")
    paper_service.delete_paper(db, paper)
