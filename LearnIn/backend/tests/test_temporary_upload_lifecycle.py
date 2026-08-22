import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.common.exceptions.exceptions import NotFoundException
from app.modules.paper.service import paper_service
from app.modules.temporary_upload.model import TemporaryUpload
from app.modules.temporary_upload.service import (
    cleanup_expired_uploads,
    create_temporary_upload,
    delete_temporary_upload,
    mark_temporary_uploads_committed,
)


class DummyDriveClient:
    def __init__(self):
        self.deleted = []

    def delete_file(self, file_id: str):
        self.deleted.append(file_id)


def test_paper_validation_rejects_missing_subject_before_duplicate_check(db_session):
    with pytest.raises(NotFoundException, match="^Subject not found$"):
        paper_service.validate_paper_available(db_session, subject_id=999999, year=2026)


def test_create_and_commit_temporary_upload(db_session):
    upload = create_temporary_upload(
        db_session,
        drive_file_id="file-commit-1",
        filename="sample.pdf",
        mime_type="application/pdf",
        file_size=123,
        upload_type="papers",
    )

    assert upload.committed is False
    expires_at = upload.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    assert expires_at > datetime.now(timezone.utc)

    mark_temporary_uploads_committed(db_session, [upload.drive_file_id])

    saved = db_session.query(TemporaryUpload).filter_by(drive_file_id="file-commit-1").one()
    assert saved.committed is True


def test_delete_temporary_upload_removed_from_drive_and_db(db_session):
    drive_client = DummyDriveClient()
    create_temporary_upload(
        db_session,
        drive_file_id="file-delete-1",
        filename="delete-me.pdf",
        mime_type="application/pdf",
        file_size=456,
        upload_type="papers",
    )

    deleted = delete_temporary_upload(db_session, drive_client, "file-delete-1")

    assert deleted is True
    assert db_session.query(TemporaryUpload).filter_by(drive_file_id="file-delete-1").count() == 0
    assert drive_client.deleted == ["file-delete-1"]


def test_delete_temporary_upload_does_not_remove_committed_file(db_session):
    drive_client = DummyDriveClient()
    upload = create_temporary_upload(
        db_session,
        drive_file_id="file-committed-delete-1",
        filename="keep-me.pdf",
        mime_type="application/pdf",
        file_size=456,
        upload_type="papers",
    )
    upload.committed = True
    db_session.commit()

    deleted = delete_temporary_upload(
        db_session,
        drive_client,
        upload.drive_file_id,
    )

    assert deleted is False
    assert drive_client.deleted == []
    assert db_session.query(TemporaryUpload).filter_by(
        drive_file_id=upload.drive_file_id
    ).count() == 1


def test_cleanup_removes_only_expired_uncommitted_uploads(db_session):
    drive_client = DummyDriveClient()
    now = datetime.now(timezone.utc)

    expired = create_temporary_upload(
        db_session,
        drive_file_id="file-expired-1",
        filename="expired.pdf",
        mime_type="application/pdf",
        file_size=10,
        upload_type="papers",
        expires_at=now - timedelta(minutes=5),
    )

    active = create_temporary_upload(
        db_session,
        drive_file_id="file-active-1",
        filename="active.pdf",
        mime_type="application/pdf",
        file_size=11,
        upload_type="papers",
        expires_at=now + timedelta(minutes=5),
    )

    committed = create_temporary_upload(
        db_session,
        drive_file_id="file-committed-1",
        filename="committed.pdf",
        mime_type="application/pdf",
        file_size=12,
        upload_type="papers",
        expires_at=now + timedelta(minutes=5),
    )
    committed.committed = True
    db_session.commit()

    deleted = asyncio.run(cleanup_expired_uploads(db_session, drive_client))

    assert deleted == 1
    assert db_session.query(TemporaryUpload).filter_by(drive_file_id=expired.drive_file_id).count() == 0
    assert db_session.query(TemporaryUpload).filter_by(drive_file_id=active.drive_file_id).count() == 1
    assert db_session.query(TemporaryUpload).filter_by(drive_file_id=committed.drive_file_id).count() == 1
    assert drive_client.deleted == [expired.drive_file_id]
