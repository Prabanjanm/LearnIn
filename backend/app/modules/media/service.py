"""
Single backend-mediated resolution point for the one file category that
actually needs an authorization check today: student avatars.

Everything else LearnIn stores a Drive file_id for (exam/department/subject
icons, paper question/answer files, question/option/explanation images, blog
thumbnails, resources) is intentionally public content served via direct
Drive URLs (see app/common/utils/drive_urls.py) - Drive file ids are long,
Drive-generated, non-sequential strings, so there is no "/media/123 ->
/media/124" IDOR risk for them, and proxying every public image through our
own server would add latency/load with no security benefit. This service
still resolves them (falling through to the public branch below) so a single
endpoint works for every Drive file id LearnIn tracks, but only the avatar
case is actually gated.
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.common.utils.file_tracking import is_file_referenced
from app.core.google_drive import get_drive_client
from app.modules.admin.model import Admin
from app.modules.student.model import Student


class MediaNotFoundError(Exception):
    """No row LearnIn tracks references this file id."""


class MediaForbiddenError(Exception):
    """The file exists and is tracked, but the caller isn't allowed to view it."""


@dataclass
class MediaFile:
    content: bytes
    mime_type: str
    cache_control: str


class MediaService:

    def resolve(
        self,
        db: Session,
        file_id: str,
        student: Student | None,
        admin: Admin | None,
    ) -> MediaFile:
        owning_student = (
            db.query(Student).filter(Student.avatar_file_id == file_id).first()
        )

        if owning_student is not None:
            is_owner = student is not None and student.id == owning_student.id
            if not (is_owner or admin is not None):
                raise MediaForbiddenError()

            return self._fetch(db, file_id, cache_control="private, max-age=3600")

        if is_file_referenced(db, file_id):
            return self._fetch(db, file_id, cache_control="public, max-age=86400")

        raise MediaNotFoundError()

    @staticmethod
    def _fetch(db: Session, file_id: str, cache_control: str) -> MediaFile:
        client = get_drive_client()
        metadata = client.get_file_metadata(file_id)
        mime_type = metadata.get("mimeType") or "application/octet-stream"
        content = client.download_file(file_id)

        return MediaFile(content=content, mime_type=mime_type, cache_control=cache_control)


media_service = MediaService()
