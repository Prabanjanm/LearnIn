import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import GoogleDriveConfigError
from app.common.rate_limit import rate_limit
from app.common.utils.file_tracking import is_file_referenced
from app.core.database import get_db
from app.core.google_drive import get_drive_client

from .dependencies import get_current_admin
from .model import Admin
from .schema import AdminLogin, AdminResponse, Token
from .service import admin_service

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"]
)

logger = logging.getLogger(__name__)


@router.post("/login", response_model=Token, dependencies=[Depends(rate_limit(10, 60))])
def login(
    data: AdminLogin,
    db: Session = Depends(get_db)
):
    return admin_service.login(db, data)


@router.get("/me", response_model=AdminResponse)
def get_me(
    current_admin: Admin = Depends(get_current_admin)
):
    return current_admin


@router.get("/files/{file_id}/download")
def download_file(
    file_id: str,
    filename: str | None = None,
    mime_type: str | None = None,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    """
    Proxies a Drive file's bytes through our own backend (rather than
    linking straight to Drive) so downloads always go through admin auth,
    work the same regardless of the file's Drive sharing permission, and
    give an attachment Content-Disposition instead of Drive's viewer page.

    filename/mime_type are optional query params: every caller in this
    codebase already knows them (they're the same *_filename/*_mime_type
    columns stored alongside the file id), so passing them skips an extra
    serial get_file_metadata round trip to Drive before the actual content
    fetch - the single biggest thing making a "click to download" feel slow.
    A caller that doesn't have them yet still works via the metadata fallback.

    file_id must belong to a row LearnIn actually tracks (is_file_referenced
    checks every *_file_id column across every entity, the same registry
    file_tracking.py already uses for cleanup) - otherwise any admin could
    pull down any file the connected Drive account can see, not just
    LearnIn's own uploads, just by guessing/enumerating Drive file ids.
    """
    if not is_file_referenced(db, file_id):
        raise HTTPException(status_code=404, detail="File not found")

    client = get_drive_client()

    try:
        if not filename or not mime_type:
            metadata = client.get_file_metadata(file_id)
            filename = filename or metadata.get("name") or file_id
            mime_type = mime_type or metadata.get("mimeType") or "application/octet-stream"

        content = client.download_file(file_id)
    except GoogleDriveConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        logger.exception("Failed to download Drive file %s", file_id)
        raise HTTPException(status_code=502, detail="Failed to download file from Drive")

    # Strip quotes (would break out of the quoted filename param) and any
    # control character including CR/LF (header-injection/response-splitting
    # attempt via a crafted Drive filename) - not just relying on the ASGI
    # server rejecting raw control chars in header values.
    safe_filename = "".join(ch for ch in filename if ch not in '"' and ord(ch) >= 32) or "download"

    return Response(
        content=content,
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )
