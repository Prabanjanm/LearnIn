import pytest
from fastapi.testclient import TestClient

from app.common.exceptions.exceptions import AlreadyExistsException
from app.core.security import hash_password
from app.main import app
from app.modules.admin.model import Admin
from app.modules.admin.service import admin_service

client = TestClient(app)


def _create_admin(db_session, email="admin@learnin.app", password="StrongPass123!"):
    admin = Admin(
        email=email,
        hashed_password=hash_password(password),
        full_name="Root Admin",
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def test_login_success_and_me(db_session):
    _create_admin(db_session)

    login_response = client.post(
        "/api/admin/login",
        json={"email": "admin@learnin.app", "password": "StrongPass123!"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get(
        "/api/admin/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "admin@learnin.app"


def test_login_wrong_password_returns_401(db_session):
    _create_admin(db_session, email="admin2@learnin.app")

    response = client.post(
        "/api/admin/login",
        json={"email": "admin2@learnin.app", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_login_unknown_email_returns_401(db_session):
    response = client.post(
        "/api/admin/login",
        json={"email": "nobody@learnin.app", "password": "whatever"},
    )
    assert response.status_code == 401


def test_me_without_token_returns_401():
    response = client.get("/api/admin/me")
    assert response.status_code == 401


def test_create_admin_duplicate_email_conflict(db_session):
    admin_service.create_admin(db_session, email="dup@learnin.app", password="Pass1234!")

    with pytest.raises(AlreadyExistsException):
        admin_service.create_admin(db_session, email="dup@learnin.app", password="Pass1234!")
