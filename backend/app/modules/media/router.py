import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import GoogleDriveConfigError
from app.core.database import get_db
from app.modules.admin.dependencies import get_optional_admin
from app.modules.admin.model import Admin
from app.modules.student.dependencies import get_optional_student
from app.modules.student.model import Student

from .service import MediaForbiddenError, MediaNotFoundError, media_service

router = APIRouter(tags=["Media"])

logger = logging.getLogger(__name__)


@router.get("/media/{file_id}")
def get_media(
    file_id: str,
    db: Session = Depends(get_db),
    student: Student | None = Depends(get_optional_student),
    admin: Admin | None = Depends(get_optional_admin),
):
    """
    Universal file_id -> bytes resolution point. Public/referenced content
    (exam icons, blog thumbnails, question images, ...) is served to anyone,
    matching today's direct-Drive-URL behavior. A student avatar is only
    served to the owning student or an admin - see service.py for why this
    is the one category that actually needs the check.
    """
    try:
        media = media_service.resolve(db, file_id, student, admin)
    except MediaNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except MediaForbiddenError:
        raise HTTPException(status_code=403, detail="You don't have permission to view this file")
    except GoogleDriveConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        logger.exception("Failed to serve media file %s", file_id)
        raise HTTPException(status_code=502, detail="Failed to fetch file")

    return Response(
        content=media.content,
        media_type=media.mime_type,
        headers={"Cache-Control": media.cache_control},
    )
