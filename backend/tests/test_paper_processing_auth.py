"""
Every new route must be closed to anonymous callers: HTML pages redirect to
the login screen, JSON endpoints answer 401.
"""
import pytest
from fastapi.testclient import TestClient

from app.common.rate_limit import reset_rate_limits
from app.main import app

client = TestClient(app)

HTML_GET_ROUTES = [
    "/admin/paper-processing",
    "/admin/paper-processing/new",
    "/admin/paper-processing/1",
    "/admin/paper-processing/1/review",
    "/admin/paper-processing/1/preview",
]

HTML_POST_ROUTES = [
    "/admin/paper-processing/new",
    "/admin/paper-processing/1/reprocess",
    "/admin/paper-processing/1/stop",
    "/admin/paper-processing/1/save",
    "/admin/paper-processing/1/generate-pdf",
    "/admin/paper-processing/1/publish",
]


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    reset_rate_limits()


@pytest.mark.parametrize("path", HTML_GET_ROUTES)
def test_html_get_routes_redirect_anonymous_users_to_login(path):
    response = client.get(path, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


@pytest.mark.parametrize("path", HTML_POST_ROUTES)
def test_html_post_routes_redirect_anonymous_users_to_login(path):
    response = client.post(path, data={}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_json_routes_reject_anonymous_users():
    assert client.get("/api/admin/paper-processing/1/status").status_code == 401
    assert client.get("/api/admin/paper-processing/1/questions").status_code == 401
    assert client.post(
        "/api/admin/paper-processing/1/questions",
        json={"question_text": "x", "options": []},
    ).status_code == 401
    assert client.put(
        "/api/admin/paper-processing/1/questions/1",
        json={"question_text": "x", "options": []},
    ).status_code == 401
    assert client.delete("/api/admin/paper-processing/1/questions/1").status_code == 401
    assert client.post(
        "/api/admin/paper-processing/1/questions/1/move", json={"direction": "up"}
    ).status_code == 401
    assert client.post("/api/admin/paper-processing/1/questions/1/split").status_code == 401
    assert client.post("/api/admin/paper-processing/1/questions/1/merge").status_code == 401
    assert client.post(
        "/api/admin/paper-processing/1/questions/1/needs-review",
        json={"needs_review": True},
    ).status_code == 401


def test_admin_file_download_proxy_requires_authentication():
    assert client.get("/api/admin/files/some-file-id/download").status_code == 401


def test_authenticated_admin_sees_the_paper_processing_pages(admin_auth_headers):
    listing = client.get("/admin/paper-processing", headers=admin_auth_headers)
    assert listing.status_code == 200
    assert "Paper Processing" in listing.text

    form = client.get("/admin/paper-processing/new", headers=admin_auth_headers)
    assert form.status_code == 200
    assert "Source question paper PDF" in form.text

    # The sidebar links to the new section.
    assert "/admin/paper-processing" in listing.text


def test_unknown_job_redirects_back_to_the_list(admin_auth_headers):
    response = client.get(
        "/admin/paper-processing/999999", headers=admin_auth_headers, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/paper-processing"


def test_upload_policy_rejects_a_non_pdf_for_the_processing_category(admin_auth_headers):
    response = client.post(
        "/admin/upload",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
        data={"category": "paper_processing_sources"},
        headers=admin_auth_headers,
    )

    assert response.status_code == 400
    assert "error" in response.json()
    assert "not allowed" in response.json()["error"]


def test_upload_policy_rejects_a_fake_pdf(admin_auth_headers):
    response = client.post(
        "/admin/upload",
        files={"file": ("evil.pdf", b"MZ\x90\x00 this is an exe", "application/pdf")},
        data={"category": "paper_processing_sources"},
        headers=admin_auth_headers,
    )

    assert response.status_code == 400
    assert "does not match a valid" in response.json()["error"]
