from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.google_drive import DriveUploadResult
from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.student.dependencies import STUDENT_ACCESS_TOKEN_COOKIE_NAME
from app.modules.student.model import Student

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limit_buckets():
    # app/common/rate_limit.py keeps a single process-global bucket dict -
    # other test modules deliberately exhaust /login, /api/students/login and
    # /api/students/signup to prove the 429 threshold works, which would
    # otherwise poison every test in this file that needs to actually log in.
    from app.common.rate_limit import _buckets
    _buckets.clear()
    yield


def _create_student(db_session, email="student@learnin.app", password="StrongPass123!"):
    student = Student(
        email=email,
        hashed_password=hash_password(password),
        full_name="Test Student",
    )
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)
    return student


def _cookies_for(student) -> dict:
    # Builds the session cookie directly instead of POSTing to /login, since
    # /login is a shared, process-global rate-limit bucket (see
    # app/common/rate_limit.py) that other test modules also exercise -
    # going through the real endpoint here would make this test's outcome
    # depend on test execution order across the whole suite.
    token = create_access_token(
        subject=str(student.id), token_type="student", token_version=student.token_version
    )
    return {STUDENT_ACCESS_TOKEN_COOKIE_NAME: token}


# --------------------------------------------------------- JSON API -----

def test_signup_success_and_me():
    response = client.post(
        "/api/students/signup",
        json={"email": "signup1@learnin.app", "password": "GoodPass123", "full_name": "New Student"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    me_response = client.get("/api/students/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    body = me_response.json()
    assert body["email"] == "signup1@learnin.app"
    assert body["full_name"] == "New Student"
    assert "created_at" in body
    assert "hashed_password" not in body
    assert "is_active" not in body


def test_duplicate_signup_conflict():
    client.post(
        "/api/students/signup",
        json={"email": "dup-student@learnin.app", "password": "GoodPass123"},
    )
    response = client.post(
        "/api/students/signup",
        json={"email": "dup-student@learnin.app", "password": "GoodPass123"},
    )
    assert response.status_code == 409


def test_weak_password_rejected_on_signup():
    response = client.post(
        "/api/students/signup",
        json={"email": "weakpass@learnin.app", "password": "short"},
    )
    assert response.status_code == 422


def test_login_wrong_password_returns_401(db_session):
    _create_student(db_session, email="wrongpass@learnin.app")

    response = client.post(
        "/api/students/login",
        json={"email": "wrongpass@learnin.app", "password": "not-the-password"},
    )
    assert response.status_code == 401


def test_me_without_token_returns_401():
    response = client.get("/api/students/me")
    assert response.status_code == 401


def test_admin_token_is_rejected_by_student_dependency(db_session):
    # Cross-domain replay: an admin-issued JWT (different "type" claim) must
    # never resolve as a student, even though both use the same secret/algorithm.
    from app.core.security import create_access_token
    from app.modules.admin.model import Admin

    admin = Admin(email="cross-domain-admin@learnin.app", hashed_password=hash_password("Pass1234!"))
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    admin_token = create_access_token(subject=str(admin.id), token_type="admin", token_version=0)

    response = client.get("/api/students/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 401


# ------------------------------------------------------- change password -----

def test_change_password_invalidates_old_token_and_issues_new_one(db_session):
    _create_student(db_session, email="changepass@learnin.app", password="OldPass123")

    login_response = client.post(
        "/api/students/login",
        json={"email": "changepass@learnin.app", "password": "OldPass123"},
    )
    old_token = login_response.json()["access_token"]

    # Old token works before the change.
    assert client.get("/api/students/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 200

    change_response = client.post(
        "/api/students/me/change-password",
        json={"current_password": "OldPass123", "new_password": "NewPass456"},
        headers={"Authorization": f"Bearer {old_token}"},
    )
    assert change_response.status_code == 200
    new_token = change_response.json()["access_token"]

    # Old token is now rejected (token_version bumped server-side).
    assert client.get("/api/students/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 401

    # New token works.
    assert client.get("/api/students/me", headers={"Authorization": f"Bearer {new_token}"}).status_code == 200

    # Old password no longer authenticates; new password does.
    assert client.post(
        "/api/students/login",
        json={"email": "changepass@learnin.app", "password": "OldPass123"},
    ).status_code == 401
    assert client.post(
        "/api/students/login",
        json={"email": "changepass@learnin.app", "password": "NewPass456"},
    ).status_code == 200


def test_change_password_wrong_current_password_rejected(db_session):
    _create_student(db_session, email="wrongcurrent@learnin.app", password="OldPass123")

    login_response = client.post(
        "/api/students/login",
        json={"email": "wrongcurrent@learnin.app", "password": "OldPass123"},
    )
    token = login_response.json()["access_token"]

    response = client.post(
        "/api/students/me/change-password",
        json={"current_password": "totally-wrong", "new_password": "NewPass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


# ----------------------------------------------------------- HTML pages -----

def test_profile_page_redirects_when_logged_out():
    response = client.get("/profile", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_html_login_sets_cookie_and_profile_loads(db_session):
    # /login shares a process-global rate-limit bucket (app/common/rate_limit.py)
    # with test_security.py's own rate-limit test, which deliberately exhausts
    # it - clear it first so this test's outcome doesn't depend on suite order.
    from app.common.rate_limit import _buckets
    _buckets.clear()

    _create_student(db_session, email="htmlflow@learnin.app", password="StrongPass123!")

    login_response = client.post(
        "/login",
        data={"email": "htmlflow@learnin.app", "password": "StrongPass123!"},
        headers={"Origin": "http://testserver"},
        follow_redirects=False,
    )
    assert login_response.status_code == 303
    assert "student_access_token" in login_response.cookies

    profile_response = client.get("/profile", cookies=login_response.cookies)
    assert profile_response.status_code == 200
    assert "htmlflow@learnin.app" in profile_response.text

    # StudentIdentityMiddleware resolves request.state.student for the
    # navbar on every page, independently of get_optional_student - it has
    # its own copy of the token-resolution logic, so this is a regression
    # test for that logic drifting out of sync (e.g. still looking a token
    # up by email after the JWT subject became a numeric id).
    home_response = client.get("/", cookies=login_response.cookies)
    assert "Log Out" in home_response.text
    assert "Log In" not in home_response.text


def test_navbar_shows_login_and_signup_when_logged_out():
    # httpx's TestClient keeps a persistent cookie jar across requests on the
    # same instance - an earlier test's real /login call would otherwise
    # leave this shared `client` looking logged-in here.
    client.cookies.clear()
    home_response = client.get("/")
    assert "Log In" in home_response.text
    assert "Sign Up" in home_response.text


def test_profile_edit_updates_name_and_avatar(db_session, monkeypatch):
    student = _create_student(db_session, email="editme@learnin.app", password="StrongPass123!")
    cookies = _cookies_for(student)

    fake_client = MagicMock()
    fake_client.upload_file.return_value = DriveUploadResult(
        file_id="avatar-file-1", mime_type="image/png", file_size=100, name="avatar.png"
    )
    monkeypatch.setattr("app.modules.pages.router.get_drive_client", lambda: fake_client)

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

    response = client.post(
        "/profile/edit",
        data={"full_name": "Updated Name"},
        files={"avatar": ("avatar.png", png_bytes, "image/png")},
        cookies=cookies,
        headers={"Origin": "http://testserver"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    profile_response = client.get("/profile", cookies=cookies)
    assert "Updated Name" in profile_response.text
    assert 'src="/media/avatar-file-1"' in profile_response.text
    fake_client.upload_file.assert_called_once()
    assert fake_client.upload_file.call_args.kwargs["public"] is False


def test_profile_edit_rejects_oversized_or_wrong_type_avatar(db_session):
    student = _create_student(db_session, email="badavatar@learnin.app", password="StrongPass123!")
    cookies = _cookies_for(student)

    response = client.post(
        "/profile/edit",
        data={"full_name": ""},
        files={"avatar": ("notes.txt", b"just some text", "text/plain")},
        cookies=cookies,
        headers={"Origin": "http://testserver"},
        follow_redirects=False,
    )
    assert response.status_code == 400
