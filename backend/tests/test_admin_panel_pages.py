from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.main import app
from app.modules.admin.model import Admin

client = TestClient(app)


def _create_panel_admin(db_session, email="panel-admin@learnin.app", password="PanelPass123!"):
    admin = Admin(
        email=email,
        hashed_password=hash_password(password),
        full_name="Panel Admin",
    )
    db_session.add(admin)
    db_session.commit()
    return admin


def test_dashboard_redirects_to_login_when_unauthenticated():
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_login_page_renders():
    response = client.get("/admin/login")
    assert response.status_code == 200
    assert "LearnIn Admin" in response.text


def test_login_sets_cookie_and_dashboard_loads(db_session):
    _create_panel_admin(db_session)

    login = client.post(
        "/admin/login",
        data={"email": "panel-admin@learnin.app", "password": "PanelPass123!"},
        follow_redirects=False,
    )
    assert login.status_code == 303
    assert "access_token" in login.cookies

    dashboard = client.get("/admin", cookies=login.cookies)
    assert dashboard.status_code == 200
    assert "Dashboard" in dashboard.text
    assert "Exams" in dashboard.text


def test_login_wrong_password_shows_error():
    response = client.post(
        "/admin/login",
        data={"email": "panel-admin@learnin.app", "password": "wrong"},
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.text


def test_create_exam_via_admin_panel_form(db_session):
    _create_panel_admin(db_session, email="panel-admin-2@learnin.app")

    login = client.post(
        "/admin/login",
        data={"email": "panel-admin-2@learnin.app", "password": "PanelPass123!"},
        follow_redirects=False,
    )
    cookies = login.cookies

    create = client.post(
        "/admin/manage/exams/new",
        data={
            "name": "Panel Created Exam",
            "code": "PCE",
            "description": "",
            "display_order": "0",
            "status": "PUBLISHED",
        },
        cookies=cookies,
        follow_redirects=False,
    )
    assert create.status_code == 303
    assert create.headers["location"] == "/admin/manage/exams?success=1"

    listing = client.get("/admin/manage/exams", cookies=cookies)
    assert listing.status_code == 200
    assert "Panel Created Exam" in listing.text

    api_check = client.get("/api/exams/")
    assert any(exam["code"] == "PCE" for exam in api_check.json())


def test_create_duplicate_exam_shows_error_on_form(db_session):
    _create_panel_admin(db_session, email="panel-admin-3@learnin.app")

    login = client.post(
        "/admin/login",
        data={"email": "panel-admin-3@learnin.app", "password": "PanelPass123!"},
        follow_redirects=False,
    )
    cookies = login.cookies

    payload = {
        "name": "Dup Panel Exam",
        "code": "DPE",
        "description": "",
        "display_order": "0",
        "status": "PUBLISHED",
    }
    client.post("/admin/manage/exams/new", data=payload, cookies=cookies)

    response = client.post("/admin/manage/exams/new", data=payload, cookies=cookies)
    assert response.status_code == 400
    assert "already exists" in response.text
