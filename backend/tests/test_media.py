from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.exam.model import Exam
from app.modules.student.dependencies import STUDENT_ACCESS_TOKEN_COOKIE_NAME
from app.modules.student.model import Student

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limit_buckets():
    from app.common.rate_limit import _buckets
    _buckets.clear()


def _create_student(db_session, email, avatar_file_id=None):
    student = Student(
        email=email,
        hashed_password=hash_password("StrongPass123!"),
        full_name="Test Student",
        avatar_file_id=avatar_file_id,
    )
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)
    return student


def _cookies_for(student) -> dict:
    token = create_access_token(
        subject=str(student.id), token_type="student", token_version=student.token_version
    )
    return {STUDENT_ACCESS_TOKEN_COOKIE_NAME: token}


def _fake_drive_client():
    fake_client = MagicMock()
    fake_client.get_file_metadata.return_value = {"mimeType": "image/png"}
    fake_client.download_file.return_value = b"fake-bytes"
    return fake_client


def test_untracked_file_id_returns_404(db_session):
    response = client.get("/media/no-such-file-id")
    assert response.status_code == 404


def test_public_referenced_file_served_without_auth(db_session, monkeypatch):
    exam = Exam(name="Media Test Exam", code="MTX", slug="media-test-exam", icon_file_id="exam-icon-1")
    db_session.add(exam)
    db_session.commit()

    fake_client = _fake_drive_client()
    monkeypatch.setattr("app.modules.media.service.get_drive_client", lambda: fake_client)

    response = client.get("/media/exam-icon-1")
    assert response.status_code == 200
    assert response.content == b"fake-bytes"
    assert response.headers["cache-control"] == "public, max-age=86400"


def test_avatar_requires_auth(db_session):
    _create_student(db_session, email="owner@learnin.app", avatar_file_id="avatar-secret-1")

    response = client.get("/media/avatar-secret-1")
    assert response.status_code == 403


def test_other_students_avatar_is_forbidden(db_session):
    _create_student(db_session, email="owner2@learnin.app", avatar_file_id="avatar-secret-2")
    other_student = _create_student(db_session, email="intruder@learnin.app")

    response = client.get("/media/avatar-secret-2", cookies=_cookies_for(other_student))
    assert response.status_code == 403


def test_owning_student_can_view_own_avatar(db_session, monkeypatch):
    student = _create_student(db_session, email="owner3@learnin.app", avatar_file_id="avatar-secret-3")

    fake_client = _fake_drive_client()
    monkeypatch.setattr("app.modules.media.service.get_drive_client", lambda: fake_client)

    response = client.get("/media/avatar-secret-3", cookies=_cookies_for(student))
    assert response.status_code == 200
    assert response.content == b"fake-bytes"
    assert response.headers["cache-control"] == "private, max-age=3600"


def test_admin_can_view_any_avatar(db_session, admin_auth_headers, monkeypatch):
    _create_student(db_session, email="owner4@learnin.app", avatar_file_id="avatar-secret-4")

    fake_client = _fake_drive_client()
    monkeypatch.setattr("app.modules.media.service.get_drive_client", lambda: fake_client)

    response = client.get("/media/avatar-secret-4", headers=admin_auth_headers)
    assert response.status_code == 200
