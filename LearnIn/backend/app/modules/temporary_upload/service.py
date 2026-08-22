from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.modules.temporary_upload.model import TemporaryUpload


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def create_temporary_upload(
    db: Session,
    drive_file_id: str,
    filename: str | None,
    mime_type: str | None,
    file_size: int | None,
    upload_type: str,
    committed: bool = False,
    expires_at: datetime | None = None,
) -> TemporaryUpload:
    if expires_at is None:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

    upload = TemporaryUpload(
        drive_file_id=drive_file_id,
        filename=filename,
        mime_type=mime_type,
        file_size=file_size,
        upload_type=upload_type,
        committed=committed,
        expires_at=expires_at,
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)
    return upload


def mark_temporary_uploads_committed(
    db: Session,
    file_ids: list[str],
    commit: bool = True,
) -> list[TemporaryUpload]:
    if not file_ids:
        return []

    uploads = (
        db.query(TemporaryUpload)
        .filter(
            TemporaryUpload.drive_file_id.in_(file_ids),
            TemporaryUpload.committed.is_(False),
        )
        .all()
    )

    for upload in uploads:
        upload.committed = True

    if uploads and commit:
        db.commit()

    return uploads


def delete_temporary_upload(db: Session, drive_service, file_id: str) -> bool:
    upload = (
        db.query(TemporaryUpload)
        .filter(
            TemporaryUpload.drive_file_id == file_id,
            TemporaryUpload.committed.is_(False),
        )
        .first()
    )

    if upload is None:
        return False

    drive_service.delete_file(file_id)
    db.delete(upload)
    db.commit()
    return True


async def cleanup_expired_uploads(db: Session, drive_service) -> int:
    now = datetime.now(timezone.utc)
    uploads = (
        db.query(TemporaryUpload)
        .filter(TemporaryUpload.committed.is_(False))
        .all()
    )

    expired_uploads = []
    for upload in uploads:
        if _normalize_utc(upload.expires_at) <= now:
            expired_uploads.append(upload)

    deleted = 0
    for upload in expired_uploads:
        try:
            drive_service.delete_file(upload.drive_file_id)
            db.delete(upload)
            deleted += 1
        except Exception as exc:
            print(f"Failed to delete Drive file {upload.drive_file_id}: {exc}")

    if expired_uploads:
        db.commit()

    return deleted
